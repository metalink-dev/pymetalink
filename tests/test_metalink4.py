import metalink


def test_should_parse_meta4_file():
    m4 = metalink.Metalink4()
    m4.parsefile(
        "tests/resources/5.15.2-0-202011130602qtxmlpatterns-Windows-Windows_7-Mingw-Windows-Windows_7-X86.7z.meta4"
    )
