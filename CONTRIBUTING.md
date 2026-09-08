# Contributing

Thank you for helping turn repositories into useful devices.

1. Create a virtual environment with Python 3.11 or newer.
2. Install the project in editable mode: `python -m pip install -e .`
3. Run `python -m unittest discover -s tests -v`.
4. Keep the core dependency-free unless a dependency removes substantial risk.
5. Add a test for every detector, manifest field, or bundle behavior.

Good first contributions include runtime detectors, sample applications,
translations, Raspberry Pi image layers, model checks, and safer installation
strategies.
