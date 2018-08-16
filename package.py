name = 'tk_core'
version = '0.18.151-wwfx'
description = 'tk-core from shotgunsoftware.'
authors = ['shotgunsoftware']
requires = ['python']

def commands():
    env.PYTHONPATH.append('{root}/lib')

build_command = 'make -f {root}/Makefile {install}'