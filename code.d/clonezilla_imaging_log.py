#!/usr/bin/env python3.6

import os
import sys
import argparse
import platform
import re
from datetime import datetime, timezone


class ClonezillaImageTime:

    def __init__(self, clonezilla_date_path, end_time_str, gv_proxy, output_csv_path):
        self.clonezilla_date_path = clonezilla_date_path
        self.end_time_str = end_time_str
        self.gv_proxy = gv_proxy
        self.output_csv_path = output_csv_path
        self.comment = ""
        self.host = platform.node()
        self.start_time = None
        self.end_time = None
        self.duration = 0

    def __add_comment(self, comment):
        if self.comment:
            self.comment += ", "
        self.comment += comment

    def __get_start_time(self):
        with open(self.clonezilla_date_path, "r") as log_file:
            start_time_str = log_file.readline().strip()
            try:
                self.start_time = datetime.strptime(start_time_str,
                                                    '%Y-%m-%dT%H:%M:%S.%f%z')
            except:
                self.start_time = None

    def __get_end_time(self):
        try:
            self.end_time = datetime.strptime(self.end_time_str,
                                              '%Y-%m-%dT%H:%M:%S.%f%z')
        except:
            # Default in case end time is not specified, or in a wrong format
            # is to get the current time
            self.end_time = datetime.now(timezone.utc).astimezone()

    def get_duration(self):
        self.__get_start_time()
        self.__get_end_time()
        if self.start_time and self.end_time:
            self.duration = self.end_time - self.start_time
            return self.duration
        else:
            self.duration = 0

        return self.duration

    def log_duration(self):
        write_header = False
        # Write header if file doesn't exist or empty
        try:
            f_stat = os.stat(self.output_csv_path)
            if f_stat.st_size == 0:
                write_header = True
        except FileNotFoundError:
            write_header = True

        try:
            with open(self.output_csv_path, "a") as csv_file:
                if write_header:
                    csv_file.write('"Hostname","Start time","End time",')
                    csv_file.write('"Duration","GV Proxy","Comment"')
                    csv_file.write("\n")

                csv_file.write(f'"{self.host}","{self.start_time}","{self.end_time}",')
                csv_file.write(f'"{self.duration}","{self.gv_proxy}","{self.comment}"')
                csv_file.write("\n")

        except:
            pass

        try:
            # This will log into syslog
            log_str=f'time="{self.start_time}"'
            log_str+=f' event=tbs_clonezilla_imaging_duration'
            log_str+=f' vers=1.0'
            log_str+=f' host="{self.host}"'
            log_str+=f' end_time="{self.end_time}"'
            log_str+=f' duration="{self.duration}"'
            log_str+=f' gv_proxy="{self.gv_proxy}"'
            log_str+=f' comment="{self.comment}"'

            import logging
            import logging.handlers
            sys_logger = logging.getLogger('SysLogger')
            sys_logger.setLevel(logging.DEBUG)
            handler = logging.handlers.SysLogHandler(address='/dev/log')
            sys_logger.addHandler(handler)
            sys_logger.info(log_str)

        except:
            pass


def _get_clonezilla_imaging_time():

    parser = argparse.ArgumentParser()
    parser.add_argument("--clonezilla-date-path",
                        help="Path to Clonezilla (start) date/time log file",
                        default="/var/opt/clonezilla-date")
    parser.add_argument("--end-time-str",
                        help="Clonezilla imaging end time. String format:" +
                             " %%Y-%%m-%%dT%%H:%%M:%%S.%%f%%z" +
                             " If not specified, default is now/current",
                        default=None)
    parser.add_argument("--gv-proxy",
                        help="GV Proxy used for re-imaging (default to get" +
                             " current proxy from the system, but might be" +
                             " different than the actual imaging proxy)",
                        default=None)
    parser.add_argument("--output-csv-path",
                        help="Path to write to log output to",
                        default="/prj/tbs/infra/power_bi/pub_source_copies/" + \
                                "clonezilla_image_time.csv")
    args = parser.parse_args()

    clonezilla_time_obj = ClonezillaImageTime(args.clonezilla_date_path,
                                              args.end_time_str,
                                              args.gv_proxy,
                                              args.output_csv_path)
    image_duration = clonezilla_time_obj.get_duration()
    clonezilla_time_obj.log_duration()
    print(f'Clonezilla image duration: {image_duration}')


if __name__ == "__main__":
    sys.exit(_get_clonezilla_imaging_time())
