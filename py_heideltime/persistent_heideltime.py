import subprocess
import threading
import queue
import uuid
import time


class PersistentHeidelTime:
    """
    Run HeidelTime in a single persistent JVM and reuse it for many documents.
    """

    def __init__(
        self,
        jar_path: str,
        language: str = "english",
        document_type: str = "news",
        dct: str | None = None,
        date_granularity: str = "full",
        java_opts: list[str] | None = None,
        config_path: str | None = None,
    ):
        self.jar_path = jar_path
        self.language = language
        self.document_type = document_type
        self.dct = dct
        self.date_granularity = date_granularity
        self.config_path = config_path or "config.props"

        java_cmd = ["java"]
        if java_opts:
            java_cmd.extend(java_opts)

        java_cmd.extend(
            [
                "-jar",
                jar_path,
                "-c",
                self.config_path,
                "-l",
                language,
                "-t",
                document_type,
                "-g",
                date_granularity,
            ]
        )

        if dct:
            java_cmd.extend(["-dct", dct])

        # Start JVM ONCE
        self.proc = subprocess.Popen(
            java_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line-buffered
        )

        self._stdout_queue = queue.Queue()
        self._reader_thread = threading.Thread(
            target=self._stdout_reader, daemon=True
        )
        self._reader_thread.start()

    def _stdout_reader(self):
        """Continuously read stdout to avoid deadlocks."""
        for line in self.proc.stdout:
            self._stdout_queue.put(line)

    def process(self, text: str, timeout: float = 30.0) -> str:
        """
        Send text to HeidelTime and return full TimeML output.
        """
        if self.proc.poll() is not None:
            raise RuntimeError("HeidelTime JVM has exited")

        # Unique delimiter to mark end of document
        marker = f"<<END-{uuid.uuid4()}>>"

        self.proc.stdin.write(text)
        self.proc.stdin.write("\n" + marker + "\n")
        self.proc.stdin.flush()

        output_lines = []
        start_time = time.time()

        while True:
            try:
                line = self._stdout_queue.get(timeout=0.1)
            except queue.Empty:
                if time.time() - start_time > timeout:
                    raise TimeoutError("HeidelTime timed out")
                continue

            if marker in line:
                break

            output_lines.append(line)

        return "".join(output_lines)

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
