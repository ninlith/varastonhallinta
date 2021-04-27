import logging
from time import perf_counter
import regex as re

logger = logging.getLogger(__name__)

class SearchHelper:
    def __init__(self):
        self.command_parts = []
        self.search_conditions = []
        self.parameters = []
        self.precompiled_regex_pattern = None
        self.no_results = False

    def execute(self, conn):
        reg = self.precompiled_regex_pattern
        if reg:
            conn.create_function(
                "REG", 1, lambda item: reg.search(item or "") is not None)
        command = "".join(self.command_parts)
        start = perf_counter()
        rows = conn.execute(command, self.parameters).fetchall()
        stop = perf_counter()
        logger.debug(f"Query time: {stop - start} s")
        return rows

    def append(self, part, parameters=None):
        self.command_parts.append(part)
        if parameters is not None:
            self.parameters.extend(parameters)

    def append_where_clause(self):
        if self.search_conditions:
            self.command_parts.append(
                "WHERE " + " AND ".join(self.search_conditions))

    def add_multiselect(self, column, valuestring, maxvalues):
        values = valuestring.split(",")
        if len(values) < maxvalues:
            try:
                values.remove("-")
            except ValueError:
                nullstring = ""
            else:
                nullstring = f" OR {column} IS NULL"
            qmarks = ", ".join(["?"]*len(values))
            self.search_conditions.append(
                f"({column} IN ({qmarks}){nullstring})")
            self.parameters.extend(values)
        elif not values:
            self.no_results = True

    def add_range(self, column, start: str = None, end: str = None):
        if start and end:
            if start == end:
                self.search_conditions.append(f"{column} = ?")
                self.parameters.append(start)
            else:
                self.search_conditions.append(f"{column} BETWEEN ? AND ?")
                self.parameters.extend([start, end])
        elif start:
            self.search_conditions.append(f"{column} >= ?")
            self.parameters.append(start)
        elif end:
            self.search_conditions.append(f"{column} <= ?")
            self.parameters.append(end)

    def set_regex(self, data, pattern, ignore_case):
        flags = (re.IGNORECASE,) if ignore_case else ()
        try:
            self.precompiled_regex_pattern = re.compile(pattern, *flags)
        except re.error as e:
            logger.debug(f"Invalid regular expression: {e}")
            self.no_results = True
        else:
            self.search_conditions.append(f"{data}")
