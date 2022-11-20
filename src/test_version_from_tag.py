import version_from_tag as target
import pytest
import helpers
import os

# --------------------------------------------------------------------------------
# Unit tests
# --------------------------------------------------------------------------------
params = [
    ('10006000/V1_00_00', (10006000, 1, 0, 0)),
    ('10006000/V13_00_00', (10006000, 13, 0, 0)),
    ('10006000/V1_00', (10006000, 1, 0, 0)),
    ('10006000/V91_00_00', (10006000, 91, 0, 0)),
    ('10009999/V1_00_00', (10009999, 1, 0, 0)),
    ('10009999/V3_14_15', (10009999, 3, 14, 15))
]

@pytest.mark.unittest
@pytest.mark.parametrize("input,expect", params)
def test_parse_version_tag(input, expect):
    """
    Test that the function 'parse_version_tag' is able to correctly parse a version tag.
    """
    test_result = target.parse_version_tag(input)
    assert test_result == expect

params = [
    (
        (
            (('annot', '10006000/V1_00_00'), ('annot', '10006020/V1_00_00')), # Commit with two annotated
            None, # Empty commit
            (('light', '10006000/V2_00_00'),), # Commit with a lightweight tag
            (('annot', '10006020/V3_00'),), # Commit with a annotated tag
            None,
            (('light', '10006000/V3_04_05'),),
            (('annot', '10006000/V3_14_25'),),
        ),
        (
            target.Version(1, 0, 0, None, 10006000, None),
            target.Version(2, 0, 0, None, 10006000, None),
            target.Version(3, 4, 5, None, 10006000, None),
            target.Version(3, 14, 25, None, 10006000, None),
            target.Version(1, 0, 0, None, 10006020, None),
            target.Version(3, 0, 0, None, 10006020, None),
        )
    )
]

@pytest.mark.unittest
@pytest.mark.parametrize("input,expect", params)
def test_get_versions_from_tags(input, expect, git_repos):
    """
    Test that the function get_version_from_tags parses and stores all tags in the git repository
    correctly.
    """

    for commit in input:
        helpers.run_git_cmd('commit --allow-empty -m "..."')
        if commit is None:
            continue

        for tag in commit:
            if tag[0] == 'annot': 
                helpers.run_git_cmd('tag -a -m "..." {}'.format(tag[1]))
            elif tag[0] == 'light':
                helpers.run_git_cmd('tag {}'.format(tag[1]))

    versions = target.get_versions_from_tags()
    assert len(versions) == 6

    for version, expected_version in zip(versions, expect):
        assert version == expected_version
        assert version.sw_article_num == expected_version.sw_article_num

# --------------------------------------------------------------------------------
# Integration tests
# --------------------------------------------------------------------------------

@pytest.mark.integrtest
def test_warn_when_version_tag_and_non_version_tag(git_repos, target_file):
    """
    If a commit is tagged with a version tag the script should issue a warning if the commit
    is also tagged with another non-version tag. Fx. the tags "10006000/V5_12_00" and "SomeOtherTag".
    """

    helpers.run_git_cmd('tag -a -m "..." 10006000/V1_00_00')
    helpers.run_git_cmd('tag -a -m "..." SomeTag')
    helpers.run_git_cmd('tag -a -m "..." SomeOtherTag')

    (error_code, error_msg, warning_msgs) = target.run(target_file)
    assert "HEAD was tagged with both version and non-version tags." in warning_msgs[0]
    assert "SomeTag" in warning_msgs[0]
    assert "SomeOtherTag" in warning_msgs[0]
    assert "10006000/V1_00_00" not in warning_msgs[0]
    assert error_msg is None
    assert error_code == 0
    return


params = [
    ('10006000/V1_00_00', '10006001/V1_00_00'),
    ('10006000/V1_01_00', '10006001/V1_01_00'),
    ('10006000/V1_00_01', '10006001/V1_00_01'),
    ('10006000/V2_00_01', '10006010/V2_00_01'),
]

@pytest.mark.integrtest
@pytest.mark.parametrize("input", params)
def test_fail_when_version_already_used(input, git_repos, target_file):
    """
    The script should fail if HEAD is tagged with a version that has already been used. This
    could happen if one commit is tagged with 10006000/V1_00_00 and another commit is tagged
    with 10006030/V1_00_00.
    """

    helpers.run_git_cmd('tag -a -m "..." {}'.format(input[0]))
    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('tag -a -m "..." {}'.format(input[1]))

    (error_code, error_msg, warning_msgs) = target.run(target_file)
    assert error_msg is not None
    assert error_code == 1
    return

@pytest.mark.integrtest
def test_fail_if_versioned_and_local_changes(git_repos, temp_file, target_file):
    """
    The script should fail if HEAD has a version tag and also has local changes either to
    the working tree or to the index (staging area). This is to avoid accidentally making changes
    after tagging.
    """

    filename = temp_file
    helpers.run_git_cmd('add {}'.format(filename))
    helpers.run_git_cmd('   commit -m "..."')

    helpers.run_git_cmd('tag -a -m "..." 10006000/V1_00_00')
    helpers.run_sys_cmd('echo "some_changes" >> {}'.format(filename))

    # Ensure that the test fails for local working tree changes
    (error_code, error_msg, warning_msgs) = target.run(target_file)
    assert error_msg is not None
    assert error_code == 2

    # Stage some changes
    helpers.run_git_cmd('add {}'.format(filename))

    # Ensure that the test fails for local index changes (staged changes)
    (error_code, error_msg, warning_msgs) = target.run(target_file)
    assert error_msg is not None
    assert error_code == 2

    return

params = [
    ('10006000/V1_00_00', '10006000/V2_00_00'),
    ('10006000/V1_00_00', '10006000/V1_01_00'),
    ('10006000/V1_00_00', '10006000/V1_00_01'),
    ('10006000/V1_00_00', '10006001/V2_00_00'),
    ('10006000/V1_00_00', '10006001/V1_01_00'),
    ('10006000/V1_00_00', '10006001/V1_00_01'),
]

@pytest.mark.integrtest
@pytest.mark.parametrize("input", params)
def test_fail_if_multiple_versions(input, git_repos, target_file):
    """
    The script should fail if HEAD is tagged with multiple versions. This could happen if HEAD is
    tagged wih 10006000/V1_00_00 and 10006000/V2_00_00.
    """

    helpers.run_git_cmd('tag -a -m "..." {}'.format(input[0]))
    helpers.run_git_cmd('tag -a -m "..." {}'.format(input[1]))

    (error_code, error_msg, warning_msgs) = target.run(target_file)
    assert error_msg is not None
    assert error_code == 3
    return

@pytest.mark.integrtest
def test_fail_if_lightweight_version_tag(git_repos, target_file):
    """
    The script should fail if HEAD is tagged with a version tag and this tag is a lightweight tag.
    Lightweight tags should be avoided because they lack information such as author, creation date,
    tag message etc.
    """

    helpers.run_git_cmd('tag 10006000/V1_00_00')

    (error_code, error_msg, warning_msgs) = target.run(target_file)
    assert error_msg is not None
    assert error_code == 4
    return

params = [
    ('10006000/V1_00_00', '10006000/V1_01_00', '10006000/V1_03_00'),
    ('10006000/V1_00_00', '10006000/V1_00_01', '10006000/V1_00_03'),
    ('10006000/V2_00_00', '10006000/V3_00_00', '10006000/V5_00_00'),
    ('10006000/V1_56_00', '10006000/V1_58_01', '10006000/V3_00_00'),
    ('10006000/V91_00_00', '10006000/V91_00_20', '10006000/V91_02_00'),
    ('10006000/V91_00_00','10006000/V91_01_00', '10006000/V91_03_00'),
    ('10006000/V91_00_10','10006000/V91_00_11', '10006000/V91_00_13'),
    ('10006001/V91_00_00','10006001/V92_00_00', '10006000/V94_00_00'),
    ('10006001/V1_00_98','10006001/V1_00_99', '10006000/V1_02_00'),
    ('10006001/V1_98_00','10006001/V1_99_00', '10006000/V3_00_00'),
]

@pytest.mark.integrtest
@pytest.mark.parametrize("input", params)
def test_fail_if_skipped_version(input, git_repos, target_file):
    """
    The script should fail if we skipped a version. For example, if the last release
    was V4_01_00 but HEAD is tagged with V4_03_00.
    """

    helpers.run_git_cmd('tag -a -m "..." {}'.format(input[0]))
    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('tag -a -m "..." {}'.format(input[1]))
    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('tag -a -m "..." {}'.format(input[2]))

    (error_code, error_msg, warning_msgs) = target.run(target_file)
    assert error_msg is not None
    assert error_code == 5
    return

params = [
    ('10006000/V1_00_00', '10006000/V2_00_00'),
    ('10006000/V1_56_00', '10006000/V2_00_00'),
]

@pytest.mark.integrtest
@pytest.mark.parametrize("input", params)
def test_accept_skipped_minor_releases_when_new_major(input, git_repos, target_file):
    """
    The script should accept if we skip minor releases to start a new major release. For example, if
    the last release was V5_14_00 the script should accept if HEAD is tagged with V6_00_00.
    """

    helpers.run_git_cmd('tag -a -m "..." {}'.format(input[0]))
    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('tag -a -m "..." {}'.format(input[1]))

    (error_code, error_msg, warning_msgs) = target.run(target_file)
    assert error_msg is None
    assert error_code == 0
    return

params = [
    (['10006000/V1_00_00'], ["#define SW_VER_MAJOR 1\n", "#define SW_VER_MINOR 0\n", "#define SW_REVISIONHASH \"{}\"\n"]),
    (['10006000/V1_00_00', '10006000/V2_00_00', '10006000/V2_01_00'], ["#define SW_VER_MAJOR 2\n", "#define SW_VER_MINOR 1\n", "#define SW_REVISIONHASH \"{}\"\n"]),
    (['10006000/V1_00_00', '10006000/V2_00_00', '10006000/V2_01_00'], ["#define SW_VER_MAJOR 2\n", "#define SW_VER_MINOR 1\n", "#define SW_REVISIONHASH \"{}\"\n"]),
    (['10006000/V91_00_00', '10006000/V91_01_00'], ["#define SW_VER_MAJOR 91\n", "#define SW_VER_MINOR 1\n", "#define SW_REVISIONHASH \"{}\"\n"]),
    (['10006000/V1_00_00', '10006000/V2_00_00', None], ["#define SW_VER_MAJOR 90\n", "#define SW_VER_MINOR 0\n", "#define SW_REVISIONHASH \"{}\"\n"]),
]

@pytest.mark.integrtest
@pytest.mark.parametrize("input,expect", params)
def test_version_file_written_and_correct(input, expect, git_repos, target_file):
    """
    Test that the version file is successfully written to disk and that the version in the file
    correponds to the tag on HEAD.
    """

    for tag in input:
        helpers.run_git_cmd('commit --allow-empty -m "..."')

        if tag is not None:
            helpers.run_git_cmd('tag -a -m "..." {}'.format(tag))
    
    # Retrieve the SHA-1 for HEAD to compare with the SHA-1 written to the version file.
    head_sha1 = helpers.run_git_cmd('rev-list --max-count=1 HEAD').strip()

    # Now run and assert that there are no errors and that the file has the expected contents.
    (error_code, error_msg, warning_msgs) = target.run(target_file)
    assert error_msg is None
    assert error_code == 0

    with open(target_file) as file:
        lines = file.readlines()

        assert lines[7] == expect[0]
        assert lines[8] == expect[1]
        assert lines[9] == expect[2].format(head_sha1[:12])

params = [
    ('10006000/V1_00_00', '10006000/V2_00_00', '10006000/V2_05_00', '10006000/V2_05_01', '10006000/V3_00_00'),
    ('10006000/V1_00_00', '10006001/V2_00_00', '10006000/V2_05_00', '10006000/V2_05_01', '10006000/V3_00_00'),
    ('10006000/V1_00_00', '10006000/V2_00_00', '10006001/V2_05_00', '10006000/V2_05_01', '10006000/V3_00_00'),
    ('10006000/V1_00_00', '10006000/V2_00_00', '10006000/V2_05_00', '10006001/V2_05_01', '10006000/V3_00_00'),
    ('10006000/V91_00_00', '10006000/V91_01_00', '10006000/V91_02_00', '10006000/V91_03_00', '10006000/V91_04_00')
]

@pytest.mark.integrtest
@pytest.mark.parametrize("input", params)
def test_accept_correct_tag_on_earlier_commit(input, git_repos, target_file):
    """
    The script should accept a version tag on HEAD even if there is a newer version in the
    repository, if that newer version is also on a newer commit than HEAD. A warning message should be
    displayed informing that there are newer versions.
    """

    for tag in input:
        helpers.run_git_cmd('commit --allow-empty -m "..."')
        helpers.run_git_cmd('tag -a -m "..." {}'.format(tag))
    helpers.run_git_cmd('checkout {}'.format(input[2]))

    (error_code, error_msg, warning_msgs) = target.run(target_file)
    assert error_msg is None
    assert error_code == 0
    assert "HEAD is tagged with version" in warning_msgs[0] and "but the most recent version is" in warning_msgs[0]

@pytest.mark.integrtest
def test_no_warnings_when_no_tags_on_head(git_repos, target_file):
    """
    The script should never issue neither errors or warnings if there are no tags on HEAD even if
    there are other tags in the repository which violate the version rules.
    """

    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('tag 10006000/V1_00_00')
    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('tag -a -m "..."" 10006000/V1_00_01')
    helpers.run_git_cmd('tag 10006000/V2_00_00')
    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('branch some_branch')
    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('tag -a -m "..."  10006001/V3_00_00')
    helpers.run_git_cmd('tag -a -m "..."  10006010/V1_10_00')
    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('tag 10006020/V3_00_00')
    helpers.run_git_cmd('checkout some_branch')

    (error_code, error_msg, warning_msgs) = target.run(target_file)
    assert error_msg is None
    assert error_code == 0
    assert len(warning_msgs) == 0

@pytest.mark.integrtest
def test_success_from_command_line(git_repos, target_file):
    """
    Test that the script can run from the command line and generate the expected file.
    """

    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('tag -a -m "..." 10006000/V1_00_00')

    # Retrieve the SHA-1 for HEAD to compare with the SHA-1 written to the version file.
    head_sha1 = helpers.run_git_cmd('rev-list --max-count=1 HEAD').strip()

    expected_stdout =  "############################################################\n"
    expected_stdout += "Software version info.\n"
    expected_stdout += "Building commit {}, tagged with version 1.00.00.\n".format(head_sha1[:12])
    expected_stdout += "############################################################"

    # Now run and assert that there are no errors and that the file has the expected contents.
    stdout = helpers.run_sys_cmd("C:\\Python38\\python.exe version_from_tag.py {}".format(target_file))

    assert stdout.strip() == expected_stdout
    
    with open(target_file) as file:
        lines = file.readlines()

        assert lines[7] == "#define SW_VER_MAJOR 1\n"
        assert lines[8] == "#define SW_VER_MINOR 0\n"
        assert lines[9] == "#define SW_REVISIONHASH \"{}\"\n".format(head_sha1[:12])

@pytest.mark.integrtest
def test_fail_from_command_line(git_repos, target_file):
    """
    Test that the script can fail from the command line and that the error message and error code is
    as expected. We test only a single failure case here because other cases are covered by other
    tests.
    """

    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('tag -a -m "..." 10006000/V1_00_00')
    helpers.run_git_cmd('commit --allow-empty -m "..."')
    helpers.run_git_cmd('tag -a -m "..." 10006000/V1_03_00')

    # Now run and assert that we get the expected error
    try:
        helpers.run_sys_cmd("C:\\Python38\\python.exe version_from_tag.py {}".format(target_file))
    except helpers.CommandError as e:
        assert "ERROR: You skipped a release version, the next version should be either 2.00.00, 1.01.00, or 1.00.01." == e.stdout.strip()
        assert e.returncode == 5