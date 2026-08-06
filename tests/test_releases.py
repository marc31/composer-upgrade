from datetime import UTC, datetime

from composer_upgrade.http import JsonClient
from composer_upgrade.releases import ReleaseService


def transport_responses(responses: dict[str, bytes]):
    def transport(request):
        return responses[request.full_url]

    return transport


def test_reads_packagist_release_dates() -> None:
    client = JsonClient(
        transport_responses(
            {
                "https://repo.packagist.org/p2/vendor/package.json": (
                    b'{"packages":{"vendor/package":[{"version":"v1.2.0",'
                    b'"time":"2026-01-02T00:00:00+00:00"}]}}'
                )
            }
        )
    )

    releases = ReleaseService(client).packagist("vendor/package")

    assert releases[0].version == "v1.2.0"
    assert releases[0].published_at == datetime(2026, 1, 2, tzinfo=UTC)


def test_reads_github_releases() -> None:
    client = JsonClient(
        transport_responses(
            {
                "https://api.github.com/repos/org/repo/releases": b'[{"tag_name":"v2.0.0","published_at":"2026-01-02T00:00:00Z","body":"Breaking","html_url":"https://example.test/release"}]'
            }
        )
    )

    releases = ReleaseService(client).changelog("https://github.com/org/repo.git")

    assert releases[0].version == "v2.0.0"
    assert releases[0].notes == "Breaking"


def test_reads_gitlab_and_bitbucket_releases() -> None:
    client = JsonClient(
        transport_responses(
            {
                "https://gitlab.com/api/v4/projects/org%2Frepo/releases": (
                    b'[{"tag_name":"v1.1.0","released_at":"2026-01-02T00:00:00Z",'
                    b'"description":"Notes","_links":{"self":"https://example.test/gitlab"}}]'
                ),
                "https://api.bitbucket.org/2.0/repositories/org/repo/refs/tags": (
                    b'{"values":[{"name":"v1.0.0","date":"2026-01-01T00:00:00Z",'
                    b'"links":{"html":{"href":"https://example.test/bitbucket"}}}]}'
                ),
            }
        )
    )

    service = ReleaseService(client)

    assert service.changelog("git@gitlab.com:org/repo.git")[0].notes == "Notes"
    assert service.changelog("https://bitbucket.org/org/repo")[0].version == "v1.0.0"
