class RepoBoxError(Exception):
    """Expected, user-facing Repo2Box error."""


class AnalysisError(RepoBoxError):
    """The source project could not be analysed safely."""


class ManifestError(RepoBoxError):
    """The Repo2Box manifest is invalid."""


class BuildError(RepoBoxError):
    """A bundle could not be produced."""


class DeployError(RepoBoxError):
    """A bundle could not be deployed."""


class ImageBuildError(RepoBoxError):
    """A bootable Raspberry Pi image could not be prepared or built."""
