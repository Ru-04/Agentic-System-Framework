from webdesk import __version__


def test_package_version_matches_baseline() -> None:
    assert __version__ == "0.3.10.0"
