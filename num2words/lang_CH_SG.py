# -*- coding: utf-8 -*-
# Copyright (c) 2003, Taro Ogawa.  All Rights Reserved.
# Copyright (c) 2013, Savoir-faire Linux inc.  All Rights Reserved.

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA

from __future__ import print_function, unicode_literals
import pandas as pd

import re

from .lang_EU import Num2Word_EU


class Num2Word_CH_SG(Num2Word_EU):
    CURRENCY_FORMS = {
        'EUR': (('Euro', 'Euro'), ('Cent', 'Cent')),
        'GBP': (('Pfund', 'Pfund'), ('Penny', 'Pence')),
        'USD': (('Dollar', 'Dollar'), ('Cent', 'Cent')),
        'CNY': (('Yuan', 'Yuan'), ('Jiao', 'Fen')),
        'DEM': (('Mark', 'Mark'), ('Pfennig', 'Pfennig')),
    }

    GIGA_SUFFIX = "illiardä"
    MEGA_SUFFIX = "illion"

    def setup(self):
        self.ordinal_declension = pd.read_excel("./helper_data/numbers_helper.xlsx", sheet_name="Ordinal_deklination"
                                                )[["Deklination","Genus","Kasus", "St_Gallen_short"]]
        
        self.ordinal_declension["Kasus"] = self.ordinal_declension["Kasus"].apply(str.lower)
        
        self.negword = "minus "
        self.posword = "plus "
        self.pointword = "Komma"
        # "Cannot treat float %s as ordinal."
        self.errmsg_floatord = (
            "Die Gleitkommazahl %s kann nicht in eine Ordnungszahl " +
            "konvertiert werden."
            )
        # "type(((type(%s)) ) not in [long, int, float]"
        self.errmsg_nonnum = (
            "Nur Zahlen (type(%s)) können in Wörter konvertiert werden."
            )
        # "Cannot treat negative num %s as ordinal."
        self.errmsg_negord = (
            "Die negative Zahl %s kann nicht in eine Ordnungszahl " +
            "konvertiert werden."
            )
        # "abs(%s) must be less than %s."
        self.errmsg_toobig = "Die Zahl %s muss kleiner als %s sein."
        self.exclude_title = []

        lows = ["Non", "Okt", "Sept", "Sext", "Quint", "Quadr", "Tr", "B", "M"]
        units = ["", "un", "duo", "tre", "quattuor", "quin", "sex", "sept",
                 "okto", "novem"]
        tens = ["dez", "vigint", "trigint", "quadragint", "quinquagint",
                "sexagint", "septuagint", "oktogint", "nonagint"]
        self.high_numwords = (
            ["zent"] + self.gen_high_numwords(units, tens, lows)
        )
        self.mid_numwords = [(1000, "tuusig"), (100, "hundert"),
                             (90, "nünzg"), (80, "achzg"), (70, "siebezg"),
                             (60, "sechzg"), (50, "füfzg"),
                             (40, "vierzg"), (30, "driisg")]
        self.low_numwords = ["zwanzg", "nünzäh", "achzäh", "siebzäh",
                             "sechzäh", "füfzäh", "vierzäh", "drizäh",
                             "zwölf", "elf", "zäh", "nün", "acht",
                             "siebe", "sechs", "füf", "vio", "drü",
                             "zwei", "eis", "null"]
        self.ords = {"eis": "ers",
                     "drei": "drit",
                     "acht": "ach",
                     "sieben": "sib",
                     "ig": "igs",
                     "ert": "erts",
                     "end": "ends",
                     "ion": "ions",
                     "nen": "ns",
                     "rde": "rds",
                     "rden": "rds",
                     "zäh":"zähn",
                     "ärd": "ärds",
                     "rdä": "rdäs"}
        
        self.minutes = { 
                        15: "viertlab",
                        25: "fünf vor halb",
                        30: "halbi",
                        35: "fünf ab halb",
                        45: "viertl vor"}
        
        self.hours = {1: "eis",
                      2: "zwei",
                        3: "drü",
                        4: "vieri",
                        5: "füfi",
                        6: "sechsi",
                        7: "sibni",
                        8: "achti", 
                        9: "nüni",
                        10: "zäni",
                        11: "elfi",
                        12: "zwölfi"}
        self.month_dates = {
            1: "Januar",
            2: "Februar",
            3: "März",
            4: "April",
            5: "Mai",
            6: "Juni",
            7: "Juli",
            8: "August",
            9: "Septämbor",
            10: "Oktobor",
            11: "Novämbor",
            12: "Dezämbor"}
        
    def merge(self, curr, next):
        ctext, cnum, ntext, nnum = curr + next

        if cnum == 1:
            if nnum == 100 or nnum == 1000:
                return ("ei" + ntext, nnum)
            elif nnum < 10 ** 6:
                return next
            ctext = "ei"

        if nnum > cnum:
            if nnum >= 10 ** 6:
                if cnum > 1:
                    if ntext.endswith("e"):
                        ntext += "n"
                    else:
                        ntext += ""
                ctext += " "
            val = cnum * nnum
        else:
            if nnum < 10 < cnum < 100:
                if nnum == 1:
                    ntext = "ein"
                ntext, ctext = ctext, ntext + "ä"
            elif cnum >= 10 ** 6:
                ctext += " "
            val = cnum + nnum

        word = ctext + ntext
        return (word, val)

    def to_ordinal(self, value, declension):
        self.verify_ordinal(value)
        outword = self.to_cardinal(value).lower()
        for key in self.ords:
            if outword.endswith(key):
                outword = outword[:len(outword) - len(key)] + self.ords[key]
                break
        mask = (self.ordinal_declension["Deklination"] == declension["declension"]) & (self.ordinal_declension["Genus"] == declension["gender"]) & (self.ordinal_declension["Kasus"] == declension["case"])
        res = outword + "t" + self.ordinal_declension[mask]["St_Gallen_short"].values[0]
        # Exception: "hundertste" is usually preferred over "einhundertste"
        if res == "eitusigssti" or (res == "eihundärdsti"):
            res = res.replace("ei", "", 1)
        # ... similarly for "millionste" etc.
        res = re.sub(r'ei ([a-z]+(illion|illiard)sti)$',
                     lambda m: m.group(1), res)
        # Ordinals involving "Million" etc. are written without a space.
        # see https://de.wikipedia.org/wiki/Million#Sprachliches
        res = re.sub(r' ([a-z]+(illion|illiard)sti)$',
                     lambda m: m.group(1), res)

        return res

    def to_ordinal_num(self, value):
        self.verify_ordinal(value)
        return str(value) + "."

    def to_currency(self, val, currency='EUR', cents=True, separator=' und',
                    adjective=False):
        result = super(Num2Word_CH_BS, self).to_currency(
            val, currency=currency, cents=cents, separator=separator,
            adjective=adjective)
        # Handle exception, in german is "ein Euro" and not "eins Euro"
        return result.replace("eis ", "ei ")
    def to_minutes(self, val):
        if val in self.minutes:
            return self.minutes[val]
        elif val < 30:
            return self.to_cardinal(val) + "ab"
        elif (val > 30) and (val < 60):
            return self.to_cardinal(60 - val) + "vor"
    def to_hours(self, val):
        if val in self.hours:
            return self.hours[val]
    def to_month_dates(self, val):
        if val in self.month_dates:
            return self.month_dates[val]

    def to_lookup(self, val):
        if val == "sek":
            return "sekunde"
    
    def to_year(self, val, longval=True):
        if not (val // 100) % 10:
            return self.to_cardinal(val)
        return self.to_splitnum(val, hightxt="hundert", longval=longval)\
            .replace(' ', '')
