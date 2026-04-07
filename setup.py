from setuptools import setup, find_namespace_packages

setup(
    name="cortellis-cli",
    version="0.1.0",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={
        "cli_anything.cortellis": ["skills/*/SKILL.md"],
    },
    include_package_data=True,
    install_requires=[
        "click>=8.1",
        "requests>=2.31",
        "rich>=13.0",
        "prompt_toolkit>=3.0",
        "python-dotenv>=1.0",
        "pyyaml>=6.0",
        "python-pptx>=0.6.21",
        "openpyxl>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-mock>=3.0",
            "responses>=0.23",
        ],
        "graph": [
            "networkx>=3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cortellis=cli_anything.cortellis.__main__:main",
        ],
    },
    python_requires=">=3.9",
)
