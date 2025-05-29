from setuptools import setup, find_packages

setup(
    name="embedchain",
    version="0.1.0",  # Placeholder version
    author="Your Name",  # Placeholder author
    description="A short description of the embedchain project.",  # Placeholder description
    packages=find_packages(),
    install_requires=[
        # Add any dependencies here
        # e.g., "requests", "numpy"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",  # Assuming MIT License, update if different
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
