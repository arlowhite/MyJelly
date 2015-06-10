#!/bin/bash
pygettext2.7 -p locale main.py $(find visuals data uix misc -name '*.py')
