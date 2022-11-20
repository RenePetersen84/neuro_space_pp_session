"""
This module extracts version information from Git tags. Tags of the form 1000ssss/Vxx_yy_zz (for
example 10006000/V1_23_45) are recognized. 'ssss' represents a the software package (for example
10006000), 'xx' is the major version number, 'yy' is the minor version number and 'zz' is the build
number. If HEAD has one or more such tags, the tags are validated based on a number of criteria. The
complete list of criteria is defined by the test module test_version_from_tag.py. Some of the most
important are given here

    * Multiple versions on HEAD are not allowed (test_fail_if_multiple_versions).
    * Already used versions cannot be used again (test_fail_when_version_already_used).
    * There can be no local changes when HEAD has a version tag
      (test_fail_if_versioned_and_local_changes).

If the criteria are met the major and minor version numbers along with the SHA-1 of HEAD is put into
the target file specified from the command line when invoking the script. The format is a C-header
file defining SW_VER_MAJOR, SW_VER_MINOR, and SW_REVISION_HASH.

The script is invoked like "python version_from_tag.py [target_file]".

The file test_version_from_tag.py contains test functions for this module. The tests are written
within the Pytest framework. To run the test suite run "pytest -v" from the command line.

##### Notes for NeuroSpace

We will implement two features which will be convenient to have before using the script in
production code.

    1. The target file is always written even if its contents are unchanged. This causes the
       timestamp to change and 'make' (which only looks at timestamps) to rebuild a potentially
       large number of .c source files. This is not practical and needs to be fixed.
    2. At the moment the script does not output any information about the last few releases. This
       information would be nice to have when building so we will implement functionality to dump
       this information to stdout.

#####
"""
from operator import index
import warnings
import re
import subprocess
import sys
import helpers

version_tag_regex = "(1000[0-9]{4})/V([1-9]?[0-9]{1})_([0-9]{2})(_([0-9][0-9]))?"
valid_sw_article_nums = [10006000, 10006001, 10006010, 10006020, 10006030]

warning_msgs = []

class VersionTagError(Exception):
    """
    This is the exception class used to indicate that there was an error with the version tag. That
    could be multiple use of the same version, local changes for a versioned commit, etc.
    """
    def __init__(self, error_code, error_msg = ""):
        self.error_code = error_code
        self.error_msg = error_msg
        super().__init__(self.error_msg)

class Version:
    """
    This class contains information about a given version. During parsing of version tags they are
    converted to instances of this class.
    """
    first_test_version = 900000

    def __init__(self, major_ver, minor_ver, build_num, creatordate=None, sw_article_num=None, sha1=None, tag_name=None):
        self._creatordate = creatordate
        self._sw_article_num = sw_article_num
        self._sha1 = sha1
        self._major_ver = major_ver
        self._minor_ver = minor_ver
        self._build_num = build_num
        self._version = major_ver*10000 + minor_ver*100 + build_num
        self._tag_name = tag_name

    def next(self, roll):
        """
        Return a Version object representing the next version when rolling either the major, minor
        or build version number by one 'roll' can be either "roll_major", "roll_minor" or
        "roll_build". 
        """
        delta = self._version
        if roll == "roll_major":
            next_ver = self._version + 10000 - (self._version % 10000)
        elif roll == "roll_minor":
            next_ver = self._version + 100 - (self._version % 100)
        elif roll == "roll_build":
            next_ver = self._version + 1
        next_major = next_ver // 10000
        next_minor = next_ver % 10000 // 100
        next_build = next_ver % 100
        return Version(next_major, next_minor, next_build, self._creatordate, self._sw_article_num, self._sha1)

    def is_kind(self, kind):
        if kind == "release":
            return self._version < Version.first_test_version
        elif kind == "test":
            return self._version > Version.first_test_version

    @property
    def sw_article_num(self):
        return self._sw_article_num

    @property
    def creator_date(self):
        return self._creatordate

    @property
    def sha1(self):
        return self._sha1

    @property
    def tag_name(self):
        return self._tag_name

    @property
    def major_ver(self):
        return self._major_ver

    @property
    def minor_ver(self):
        return self._minor_ver

    @property
    def kind(self):
        """
        Gives the kind of version that this object represents; "release" if it is a
        release version and "test" if it is a test version
        """
        if self._version < self.first_test_version:
            return "release"
        else:
            return "test"

    def __eq__(self, other):
        return self._version == other._version

    def __gt__(self, other):
        return self._version > other._version
    
    def __lt__(self, other):
        return self._version < other._version

    def __ge__(self, other):
        return self.verison >= other._version

    def __le__(self, other):
        return self._version <= other._version

    def __ne__(self, other):
        return self._version != other._version

    def __str__(self):
        return "{}.{:02d}.{:02d}".format(self._major_ver, self._minor_ver, self._build_num)

def parse_version_tag(version_tag):
    """
    Parses a version tag and returns a tuple of the form (sw_article_num, major_ver, minor_ver,
    build_number).
    """
    p = re.compile(version_tag_regex)

    match_obj = p.match(version_tag)
    
    if (match_obj is not None):
        groups = match_obj.groups(default='00')

        sw_article_num = int(groups[0])
        major_ver = int(groups[1])
        minor_ver = int(groups[2])
        build_num = int(groups[4])
        
        return (sw_article_num, major_ver, minor_ver, build_num)
    else:
        return None

def is_sw_article_num_valid(sw_article_num):
    if sw_article_num in valid_sw_article_nums:
        return True


def get_versions_from_tags():
    """
    Use Git to get all tags and parse them to extract all version info.
    """
    process = subprocess.run(["git", "for-each-ref", "--sort=refname", "--format=%(creatordate:unix);%(object);%(objectname);%(refname)"], stdout=subprocess.PIPE, universal_newlines=True)
        
    versions = []
    for line in process.stdout.splitlines():
        split_line = line.split(';')

        creatordate_field = split_line[0]
        object_field = split_line[1]
        objectname_field = split_line[2]
        refname_field = split_line[3]

        if (object_field != ""):
            sha1 = object_field
        else:
            sha1 = objectname_field

        tag_name = refname_field.replace("refs/tags/", "")
        parsed_tag = parse_version_tag(tag_name)

        if (parsed_tag is not None):
            (sw_article_num, major_ver, minor_ver, build_num) = parsed_tag
            if is_sw_article_num_valid(sw_article_num):
                version = Version(major_ver, minor_ver, build_num, creatordate_field, sw_article_num, sha1, tag_name)
                versions.append(version)

    return versions

def get_head_versions(versions, head_sha1):
    """
    Retrieve version information on HEAD.
    """
    head_versions = []
    for version in versions:
        if version.sha1 == head_sha1:
            head_versions.append(version)

    if len(head_versions) > 0:
        for head_version in head_versions:
            versions.remove(head_version)
    else:
        head_versions = None

    return head_versions

def get_head_sha1():
    process = subprocess.run(["git", "rev-list", "--max-count=1", "HEAD"], stdout=subprocess.PIPE, universal_newlines=True)
    sha1_head = process.stdout.strip()

    return sha1_head

def get_head_has_local_changes():
    workingtree_changes = helpers.run_git_cmd('diff').strip()
    index_changes = helpers.run_git_cmd('diff --cached').strip()

    return (workingtree_changes, index_changes)

def get_head_nonversion_tags():
    head_tags = helpers.run_git_cmd("tag --points-at HEAD")

    nonversion_tags = []
    for head_tag in head_tags.splitlines():
        if parse_version_tag(head_tag) == None:
            nonversion_tags.append(head_tag)

    return nonversion_tags

def check_head_version_already_used(head_version, prev_versions):
    for version in prev_versions:
        if version == head_version:
            raise VersionTagError(1, "The version {} has already been used".format(head_version))

def check_head_has_multiple_versions(head_versions):
    for version in head_versions:
        if version != head_versions[0]:
            raise VersionTagError(3, "HEAD seems to be tagged with multiple versions. At least the tag {} and {} have different versions.".format(version.tag_name, head_versions[0].tag_name))

def check_head_version_skipped_a_version(head_version, prev_versions):
    # Find the most recent version among the previous versions

    head_version_kind = head_version.kind
    most_recent_version = Version(0, 0, 0)
    for prev_version in prev_versions:
        if prev_version.is_kind(head_version_kind) and prev_version > most_recent_version:
            most_recent_version = prev_version

    # The head versions is earlier or identical to the most recent versions, then we cannot have skipped
    # a version. Probably an earlier version has been checked out. We do, however, issue a warning
    # informing about this.
    if head_version <= most_recent_version:
        warning_msgs.append("HEAD is tagged with version {} but the most recent version is {}. Was this the intention (you might have checked out an earlier commit)?".format(head_version, most_recent_version))
        return

    if head_version.kind == "release":
        valid_next_versions = [most_recent_version.next("roll_major"), most_recent_version.next("roll_minor"), most_recent_version.next("roll_build")]
        if head_version > most_recent_version and not head_version in valid_next_versions:
            raise VersionTagError(5, "You skipped a release version, the next version should be either {}, {}, or {}.".format(str(valid_next_versions[0]), str(valid_next_versions[1]), str(valid_next_versions[2])))
    else:
        valid_next_versions = [most_recent_version.next("roll_minor"), most_recent_version.next("roll_build")]
        if not head_version in valid_next_versions:
            raise VersionTagError(5, "You skipped a test version, the next version should be either {} or {}.".format(str(valid_next_versions[0]), str(valid_next_versions[1])))

def check_tag_is_lightweight(head_versions):
    for head_version in head_versions:
        objecttype = helpers.run_git_cmd('for-each-ref --format="%(objecttype)" refs/tags/{}'.format(head_version.tag_name))
        if objecttype.strip() == "commit": # for a lightweight tag the objecttype is "commit", for an annotated tag it is "tag"
            raise VersionTagError(4, "You assigned a lightweight tag ({}) to HEAD, you should use annotated tags (git tag -a)".format(head_version.tag_name))

def check_head_has_local_changes(workingtree_has_changes, index_has_changes):
    if workingtree_has_changes != "":
        raise VersionTagError(2, "HEAD is tagged but has local changes. This is not allowed.")

    if index_has_changes != "":
        raise VersionTagError(2, "HEAD is tagged but has staged changes. This is not allowed.")

def check_head_has_version_and_nonversion_tag():
    """
    Check if HEAD has both a version tag and a non-version tag.
    """

    non_version_tags = []
    head_tags = helpers.run_git_cmd('tag --points-at HEAD')
    for head_tag in head_tags.splitlines():
        if parse_version_tag(head_tag) == None:
            non_version_tags.append(head_tag)

    if len(non_version_tags) > 0:
        warning_msgs.append("HEAD was tagged with both version and non-version tags. Was this the intent? The non-version tags are: {}".format(non_version_tags))

def write_version_file(target_file, head_versions, head_sha1, workingtree_has_changes, index_has_changes):
    has_local_changes = workingtree_has_changes or index_has_changes

    if head_versions is None:
        major_ver = 90
        minor_ver = 0
    else:
        major_ver = head_versions[0].major_ver
        minor_ver = head_versions[0].minor_ver

    file_content =  "//--------------------------------------------------------------------------------------------------\n"
    file_content += "// Notes:\n"
    file_content += "// This file is autogenerated by the Python script \"version_from_tag.py\" invoked during building.\n"
    file_content += "// Do not edit this file as changes will be overwritten during building.\n"
    file_content += "//--------------------------------------------------------------------------------------------------\n"
    file_content += "#ifndef _SWPACKAGEVERSION_H_\n"
    file_content += "#define _SWPACKAGEVERSION_H_\n"
    file_content += "#define SW_VER_MAJOR {:d}\n".format(major_ver)
    file_content += "#define SW_VER_MINOR {:d}\n".format(minor_ver)
    file_content += "#define SW_REVISIONHASH \"{:s}\"\n".format("+" + head_sha1 if has_local_changes else head_sha1[:12])
    file_content += "#endif"

    with open(target_file, "w") as file:
        file.write(file_content)

def print_version_information(versions, head_versions, head_sha1):
    if head_versions is None:
        head_version_str = "90.00.00"
    else:
        head_version_str = str(head_versions[0])

    output =  "############################################################\n"
    output += "Software version info.\n"
    output += "Building commit {:s}, tagged with version {}.\n".format(head_sha1[:12], head_version_str)
    output += "############################################################"
    print(output)

def check_head(versions, head_versions, head_sha1, workingtree_has_changes, index_has_changes):
    """
    If HEAD has a version tag this function checks that the tag obeys the rules.
    """

    if head_versions is not None:
        check_head_version_already_used(head_versions[0], versions)
        check_head_version_skipped_a_version(head_versions[0], versions)
        check_tag_is_lightweight(head_versions)
        check_head_has_multiple_versions(head_versions)
        check_head_has_local_changes(workingtree_has_changes, index_has_changes)
        check_head_has_version_and_nonversion_tag()

def run(target_file):
    global warning_msgs

    error_code = 0
    error_msg = None
    warning_msgs = []

    versions = get_versions_from_tags()
    head_sha1 = get_head_sha1()
    head_versions = get_head_versions(versions, head_sha1)
    (workingtree_changes, index_changes) = get_head_has_local_changes()

    try:
        check_head(versions, head_versions, head_sha1, workingtree_changes, index_changes)
        write_version_file(target_file, head_versions, head_sha1, workingtree_changes, index_changes)
        print_version_information(versions, head_versions, head_sha1)
    except VersionTagError as e:
        error_code = e.error_code
        error_msg = e.error_msg

    return (error_code, error_msg, warning_msgs)

def main(target_file):
    (error_code, error_msg, warning_msgs) = run(target_file)

    for warning_msg in warning_msgs:
        print("WARNING: {}".format(warning_msg))

    if error_code != 0:
        print("ERROR: {}".format(error_msg))
        sys.exit(error_code)

if __name__  == "__main__":
    main(sys.argv[1])