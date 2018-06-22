#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import subprocess
import tempfile
import unittest


class BlackListCompacterTests(unittest.TestCase):
    def test_unix_utils(self):
        list_tmp_files = []
        tempfilefd_file_out, tempfile_file_out = tempfile.mkstemp(".csv_", "bl-")
        list_tmp_files.append(( tempfilefd_file_out, tempfile_file_out ))
        f_sout = open(tempfile_file_out, "w")
        out = subprocess.call("which diff", stdout=f_sout, shell=True)
        self.assert_(out == 0, "diff on the board")
        out = subprocess.call("which patch", stdout=f_sout, shell=True)
        self.assert_(out == 0, "patch on the board")

        for fd, fn in list_tmp_files:
            if os.path.exists(fn):
                os.remove(fn)

    def test_csv(self):
        file1 = """id,link
1,http://link1.pl
2,http://link2.pl
3,http://link3.pl
4,http://link4.pl
"""
        file2 = """id,link
2,http://link2.pl
3,http://link3.pl
6,http://link6.pl
"""
        file_out = """@@ -1,5 +1,4 @@
 id,link
-1,http://link1.pl
 2,http://link2.pl
 3,http://link3.pl
-4,http://link4.pl
+6,http://link6.pl
"""

        list_tmp_files = []
        tempfilefd_file1, tempfile_file1 = tempfile.mkstemp(".csv_", "bl-")
        tempfilefd_file2, tempfile_file2 = tempfile.mkstemp(".csv_", "bl-")
        tempfilefd_file_out, tempfile_file_out = tempfile.mkstemp(".csv_", "bl-")
        list_tmp_files.append(( tempfilefd_file1, tempfile_file1 ))
        list_tmp_files.append(( tempfilefd_file2, tempfile_file2 ))
        list_tmp_files.append(( tempfilefd_file_out, tempfile_file_out ))

        for fd, fn in list_tmp_files:
            os.close(fd)
            os.chmod(fn, 0644)

        with open(tempfile_file1, 'w') as ftn:
            ftn.write(file1)
        with open(tempfile_file2, 'w') as ftn:
            ftn.write(file2)

        with open(tempfile_file1, 'r') as ftn:
            self.assert_(ftn.read() == file1, "file1 wrong")
        with open(tempfile_file2, 'r') as ftn:
            self.assert_(ftn.read() == file2, "file2 wrong")
        with open(tempfile_file_out, 'r') as ftn:
            self.assert_(ftn.read() == "", "file2 wrong")

        f_sout = open(tempfile_file_out, "w")
        out = subprocess.call("diff -u " + tempfile_file1 + " " +
                              tempfile_file2, stdout=f_sout, shell=True)
        self.assert_(out == 1, """system diff exec.     0     No differences were found. 
    1     Differences were found.
   >1     An error occurred.""")

        with open(tempfile_file_out, 'r') as ftn:
            self.assert_(file_out in ftn.read(), "file_out wrong")

        for fd, fn in list_tmp_files:
            if os.path.exists(fn):
                os.remove(fn)

    def test_csv_the_same_files(self):
        file1 = """id,link
1,http://link1.pl
2,http://link2.pl
3,http://link3.pl
4,http://link4.pl
"""
        file2 = """id,link
1,http://link1.pl
2,http://link2.pl
3,http://link3.pl
4,http://link4.pl
"""
        file_out = """"""

        list_tmp_files = []
        tempfilefd_file1, tempfile_file1 = tempfile.mkstemp(".csv_", "bl-")
        tempfilefd_file2, tempfile_file2 = tempfile.mkstemp(".csv_", "bl-")
        tempfilefd_file_out, tempfile_file_out = tempfile.mkstemp(".csv_", "bl-")
        list_tmp_files.append(( tempfilefd_file1, tempfile_file1 ))
        list_tmp_files.append(( tempfilefd_file2, tempfile_file2 ))
        list_tmp_files.append(( tempfilefd_file_out, tempfile_file_out ))

        for fd, fn in list_tmp_files:
            os.close(fd)
            os.chmod(fn, 0644)

        with open(tempfile_file1, 'w') as ftn:
            ftn.write(file1)
        with open(tempfile_file2, 'w') as ftn:
            ftn.write(file2)

        with open(tempfile_file1, 'r') as ftn:
            self.assert_(ftn.read() == file1, "file1 wrong")
        with open(tempfile_file2, 'r') as ftn:
            self.assert_(ftn.read() == file2, "file2 wrong")
        with open(tempfile_file_out, 'r') as ftn:
            self.assert_(ftn.read() == "", "file2 wrong")

        f_sout = open(tempfile_file_out, "w")
        out = subprocess.call("diff -u " + tempfile_file1 + " " +
                              tempfile_file2, stdout=f_sout, shell=True)
        self.assert_(out == 0, """system diff exec.     0     No differences were found. 
    1     Differences were found.
   >1     An error occurred.""")

        with open(tempfile_file_out, 'r') as ftn:
            self.assert_(ftn.read() == file_out, "file_out wrong")

        for fd, fn in list_tmp_files:
            if os.path.exists(fn):
                os.remove(fn)

    def test_csv_the_1files_empty(self):
        file1 = """"""
        file2 = """id,link
1,http://link1.pl
2,http://link2.pl
3,http://link3.pl
4,http://link4.pl
"""
        file_out = """@@ -0,0 +1,5 @@
+id,link
+1,http://link1.pl
+2,http://link2.pl
+3,http://link3.pl
+4,http://link4.pl
"""

        list_tmp_files = []
        tempfilefd_file1, tempfile_file1 = tempfile.mkstemp(".csv_", "bl-")
        tempfilefd_file2, tempfile_file2 = tempfile.mkstemp(".csv_", "bl-")
        tempfilefd_file_out, tempfile_file_out = tempfile.mkstemp(".csv_", "bl-")
        list_tmp_files.append(( tempfilefd_file1, tempfile_file1 ))
        list_tmp_files.append(( tempfilefd_file2, tempfile_file2 ))
        list_tmp_files.append(( tempfilefd_file_out, tempfile_file_out ))

        for fd, fn in list_tmp_files:
            os.close(fd)
            os.chmod(fn, 0644)

        with open(tempfile_file1, 'w') as ftn:
            ftn.write(file1)
        with open(tempfile_file2, 'w') as ftn:
            ftn.write(file2)

        with open(tempfile_file1, 'r') as ftn:
            self.assert_(ftn.read() == file1, "file1 wrong")
        with open(tempfile_file2, 'r') as ftn:
            self.assert_(ftn.read() == file2, "file2 wrong")
        with open(tempfile_file_out, 'r') as ftn:
            self.assert_(ftn.read() == "", "file2 wrong")

        f_sout = open(tempfile_file_out, "w")
        out = subprocess.call("diff -u " + tempfile_file1 + " " +
                              tempfile_file2, stdout=f_sout, shell=True)
        self.assert_(out == 1, """system diff exec.     0     No differences were found. 
    1     Differences were found.
   >1     An error occurred.""")

        with open(tempfile_file_out, 'r') as ftn:
            self.assert_(file_out in ftn.read(), "file_out wrong")

        for fd, fn in list_tmp_files:
            if os.path.exists(fn):
                os.remove(fn)

    def test_xml(self):
        file1 = """<?xml version="1.0"?>
<!DOCTYPE PARTS SYSTEM "parts.dtd">
<?xml-stylesheet type="text/css" href="xmlpartsstyle.css"?>
<PARTS>
   <TITLE>Computer Parts</TITLE>
   <PART>
      <ITEM>Motherboard</ITEM>
      <MANUFACTURER>ASUS</MANUFACTURER>
      <MODEL>P3B-F</MODEL>
      <COST> 123.00</COST>
   </PART>
   <PART>
      <ITEM>Video Card</ITEM>
      <MANUFACTURER>ATI</MANUFACTURER>
      <MODEL>All-in-Wonder Pro</MODEL>
      <COST> 160.00</COST>
   </PART>
   <PART>
      <ITEM>Sound Card</ITEM>
      <MANUFACTURER>Creative Labs</MANUFACTURER>
      <MODEL>Sound Blaster Live</MODEL>
      <COST> 80.00</COST>
   </PART>
   <PART>
      <ITEM inch Monitor</ITEM>
      <MANUFACTURER>LG Electronics</MANUFACTURER>
      <MODEL> 995E</MODEL>
      <COST> 290.00</COST>
   </PART>
</PARTS>
"""
        file2 = """<?xml version="1.0"?>
<!DOCTYPE PARTS SYSTEM "parts.dtd">
<?xml-stylesheet type="text/css" href="xmlpartsstyle.css"?>
<PARTS>
   <TITLE>Computer Parts</TITLE>
   <PART>
      <ITEM>Motherboard</ITEM>
      <MANUFACTURER>ASUS</MANUFACTURER>
      <MODEL>P3B-F</MODEL>
      <COST> 123.00</COST>
   </PART>
   <PART>
      <ITEM>Sound Card</ITEM>
      <MANUFACTURER>Creative Labs</MANUFACTURER>
      <MODEL>Sound Blaster Live</MODEL>
      <COST> 80.00</COST>
   </PART>
   <PART>
      <ITEM inch Monitor</ITEM>
      <MANUFACTURER>LG Electronics</MANUFACTURER>
      <MODEL> 995E</MODEL>
      <COST> 290.00</COST>
   </PART>
</PARTS>
"""
        file_out = """@@ -10,12 +10,6 @@
       <COST> 123.00</COST>
    </PART>
    <PART>
-      <ITEM>Video Card</ITEM>
-      <MANUFACTURER>ATI</MANUFACTURER>
-      <MODEL>All-in-Wonder Pro</MODEL>
-      <COST> 160.00</COST>
-   </PART>
-   <PART>
       <ITEM>Sound Card</ITEM>
       <MANUFACTURER>Creative Labs</MANUFACTURER>
       <MODEL>Sound Blaster Live</MODEL>
"""

        list_tmp_files = []
        tempfilefd_file1, tempfile_file1 = tempfile.mkstemp(".csv_", "bl-")
        tempfilefd_file2, tempfile_file2 = tempfile.mkstemp(".csv_", "bl-")
        tempfilefd_file_out, tempfile_file_out = tempfile.mkstemp(".csv_", "bl-")
        list_tmp_files.append(( tempfilefd_file1, tempfile_file1 ))
        list_tmp_files.append(( tempfilefd_file2, tempfile_file2 ))
        list_tmp_files.append(( tempfilefd_file_out, tempfile_file_out ))

        for fd, fn in list_tmp_files:
            os.close(fd)
            os.chmod(fn, 0644)

        with open(tempfile_file1, 'w') as ftn:
            ftn.write(file1)
        with open(tempfile_file2, 'w') as ftn:
            ftn.write(file2)

        with open(tempfile_file1, 'r') as ftn:
            self.assert_(ftn.read() == file1, "file1 wrong")
        with open(tempfile_file2, 'r') as ftn:
            self.assert_(ftn.read() == file2, "file2 wrong")
        with open(tempfile_file_out, 'r') as ftn:
            self.assert_(ftn.read() == "", "file_out wrong")

        f_sout = open(tempfile_file_out, "w")
        out = subprocess.call("diff -u " + tempfile_file1 + " " +
                              tempfile_file2, stdout=f_sout, shell=True)
        self.assert_(out == 1, """system diff exec.     0     No differences were found. 
    1     Differences were found.
   >1     An error occurred.""")

        with open(tempfile_file_out, 'r') as ftn:
            self.assert_(file_out in ftn.read(), "file_out wrong")

        for fd, fn in list_tmp_files:
            if os.path.exists(fn):
                os.remove(fn)


def main():
    unittest.main()


if __name__ == '__main__':
    main()