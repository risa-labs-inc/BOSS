#!/usr/bin/env python3
"""
Simple script to run the BOSS Python Agent.

This script allows running the agent directly from the command line without
having to use the module syntax (python -m boss_py_agent).
"""

import sys
from boss_py_agent.boss_py_agent import main

if __name__ == "__main__":
    sys.exit(main()) 