import multiprocessing
import platform
import re
import tempfile
from datetime import date
from itertools import repeat
from pathlib import Path
from typing import List

from py_heideltime.config import _write_config_props
from py_heideltime.meta import LANGUAGES, DOC_TYPES
from py_heideltime.utils import process_text, execute_command


LIBRARY_PATH = Path(__file__).parent

TAGGER_PATH = LIBRARY_PATH / "Heideltime" / "TreeTaggerLinux"
HEIDELTIME_JAR_PATH = LIBRARY_PATH / "Heideltime" / "de.unihd.dbs.heideltime.standalone.jar"

# JPype-based persistent JVM instance
_jvm_started = False
_heideltime_instance = None


def _validate_inputs(
        language: str,
        document_type: str
) -> None:
    """Check if the language and document type are valid. If not, the function will raise a value error."""
    if language.lower() not in LANGUAGES:
        msg = f"Invalid language. Language should be within the following values: {LANGUAGES}"
        raise ValueError(msg)

    if document_type.lower() not in DOC_TYPES:
        msg = f"Invalid document type. Language should be within the following values: {LANGUAGES}"
        raise ValueError(msg)


def _start_jvm():
    """Start the JVM once using JPype."""
    global _jvm_started
    if _jvm_started:
        return
    
    import jpype
    import jpype.imports
    
    if not jpype.isJVMStarted():
        jpype.startJVM(
            classpath=[str(HEIDELTIME_JAR_PATH)],
            convertStrings=True
        )
    _jvm_started = True


def _get_heideltime_instance(language: str, document_type: str, dct: str | None, date_granularity: str):
    """Get or create HeidelTime instance via JPype."""
    global _heideltime_instance
    
    _start_jvm()
    _write_config_props()
    
    import jpype
    
    # Import Java classes
    HeidelTimeStandalone = jpype.JClass("de.unihd.dbs.heideltime.standalone.HeidelTimeStandalone")
    Language = jpype.JClass("de.unihd.dbs.uima.annotator.heideltime.resources.Language")
    DocumentType = jpype.JClass("de.unihd.dbs.heideltime.standalone.DocumentType")
    OutputType = jpype.JClass("de.unihd.dbs.heideltime.standalone.OutputType")
    POSTagger = jpype.JClass("de.unihd.dbs.heideltime.standalone.POSTagger")
    
    # Map language string to enum
    lang_map = {
        "english": Language.ENGLISH,
        "german": Language.GERMAN,
        "french": Language.FRENCH,
        "italian": Language.ITALIAN,
        "spanish": Language.SPANISH,
        "dutch": Language.DUTCH,
        "portuguese": Language.PORTUGUESE,
    }
    
    doc_type_map = {
        "news": DocumentType.NEWS,
        "narrative": DocumentType.NARRATIVES,
        "colloquial": DocumentType.COLLOQUIAL,
        "scientific": DocumentType.SCIENTIFIC,
    }
    
    lang_enum = lang_map.get(language.lower(), Language.ENGLISH)
    doc_enum = doc_type_map.get(document_type.lower(), DocumentType.NEWS)
    
    # Create HeidelTime instance (reuse if already created with same params)
    if _heideltime_instance is None:
        config_path = str(Path("config.props").resolve())
        _heideltime_instance = HeidelTimeStandalone(
            lang_enum,
            doc_enum,
            OutputType.TIMEML,
            config_path
        )
    
    return _heideltime_instance


def heideltime(
    text: str,
    language: str = "german",
    document_type: str = "news",
    dct: str | None = None,
    date_granularity: str = "full",
):
    """
    Run HeidelTime temporal tagger using a persistent JVM (via JPype).
    
    The JVM is started once on first call and reused for all subsequent calls,
    making repeated calls much faster.
    
    Args:
        text: The text to process
        language: Language of the text (english, german, french, etc.)
        document_type: Type of document (news, narrative, colloquial, scientific)
        dct: Document creation time in YYYY-MM-DD format (defaults to today)
        date_granularity: Granularity of date output
    """
    _validate_inputs(language, document_type)
    
    ht = _get_heideltime_instance(language, document_type, dct, date_granularity)
    
    import jpype
    
    # Convert DCT to java.util.Date
    if dct is None:
        # Use current date
        java_date = jpype.JClass("java.util.Date")()
    else:
        # Parse the date string to java.util.Date
        SimpleDateFormat = jpype.JClass("java.text.SimpleDateFormat")
        sdf = SimpleDateFormat("yyyy-MM-dd")
        java_date = sdf.parse(dct)
    
    # Process the text
    tml_doc = ht.process(text, java_date)
    
    # Extract TimeML content
    start = tml_doc.find("<TimeML>")
    end = tml_doc.rfind("</TimeML>")
    if start == -1 or end == -1:
        raise RuntimeError(
            "HeidelTime did not return a <TimeML> block.\n"
            "Raw output:\n" + tml_doc
        )

    tml_content = tml_doc[start + 8 : end]
    return _get_timexs(tml_content)



# def heideltime(
#         text: str,
#         language: str = "english",
#         document_type: str = "news",
#         dct: str = None,
#         date_granularity="full"
# ):
#     """Run HeidelTime temporal tagger."""
#     _validate_inputs(language, document_type)
#     _write_config_props()

#     with tempfile.TemporaryDirectory(dir=LIBRARY_PATH) as tempdir:
#         processed_text = process_text(text)
#         filepaths = _create_text_files(processed_text, tempdir)

#         processes = multiprocessing.cpu_count()
#         with multiprocessing.Pool(processes=processes) as pool:
#             inputs_ = zip(filepaths, repeat(language), repeat(document_type), repeat(dct),repeat(date_granularity))
#             tml_docs = pool.starmap(
#                 _exec_java_heideltime,
#                 inputs_
#             )

#         tml_parts = []
#         for tml_doc in tml_docs:
#             matches = re.findall(r"<TimeML>(.*)</TimeML>", tml_doc, re.DOTALL)
#             if not matches:
#                 raise RuntimeError(
#                     "HeidelTime did not return a <TimeML> block for one of the inputs.\n"
#                     "Raw Java output below:\n" + (tml_doc or "<empty output>")
#                 )
#             tml_parts.append(matches[0].strip("\n"))

#         tml_content = "".join(tml_parts)

#         timexs = _get_timexs(tml_content)

#     Path("config.props").unlink()
#     return timexs


def _create_text_files(text: str, dir_path: Path) -> List:
    """Writes text files to be annotated by Java implementation of HeidelTime."""
    max_n_characters = 30_000
    n_characters = len(text)
    chunks = [text[i:i + max_n_characters] for i in range(0, n_characters, max_n_characters)]

    filepaths = []
    for chunk in chunks:
        temp = tempfile.NamedTemporaryFile(dir=dir_path, delete=False)
        temp.write(chunk.encode("utf-8"))
        temp.close()
        filepaths.append(Path(temp.name))
    return filepaths


def _exec_java_heideltime(
        filename: str,
        language: str,
        document_type: str,
        dct: str,
        date_granularity: str
) -> str:
    """Execute Java implementation of HeidelTime."""
    if dct is not None:
        match = re.findall(r"^\d{4}-\d{2}-\d{2}$", dct)
        if not match:
            raise ValueError("Please specify date in the following format: YYYY-MM-DD.")
        java_cmd = f"java -jar {HEIDELTIME_JAR_PATH} -dct {dct} -t {document_type} -l {language} {filename}"
    else:
        java_cmd = f"java -jar {HEIDELTIME_JAR_PATH} -t {document_type} -l {language} {filename}"

    time_ml = execute_command(java_cmd)  # TimeML text from java output

    return time_ml


def _get_timexs(time_ml):
    # Find tags from java output
    tags = re.findall("<TIMEX3 (.*?)>(.*?)</TIMEX3>", time_ml)

    # Get timexs with attributes.
    timexs = []
    for attribs, text in tags:
        timex = {"text": text}
        for attrib in attribs.split():
            key, value = attrib.split("=")
            value = value.strip("\"")
            timex[key] = value
        timexs.append(timex)

    # Add spans to timexs.
    text_blocks = re.split("<TIMEX3.*?>(.*?)</TIMEX3>", time_ml)
    running_span = 0
    timexs_with_spans = []
    if not timexs:
        return timexs_with_spans

    else:
        timex = timexs.pop(0)
        for block in text_blocks:
            if block == timex["text"]:
                timex["span"] = [running_span, running_span + len(block)]
                timexs_with_spans.append(timex)
                if timexs:
                    timex = timexs.pop(0)
                else:
                    break
            running_span += len(block)

    return timexs_with_spans
