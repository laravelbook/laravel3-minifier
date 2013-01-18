import os
import re
import subprocess
import pickle
from sys import platform

RE_NAMESPACE = re.compile(r'\snamespace\s+([^;$@"*%\',:]+);')
RE_NAMESPACE_USAGE = re.compile(r'\suse\s+([^;$@"*%\':]+);')
RE_NAMESPACE_OR_USAGE = re.compile(r'(namespace|use)\s+[^;$@"*%\',:]+;')

NAMESPACE_SKIPLIST = [r'helpers\.php']
RE_NAMESPACE_SKIPLIST = []

FILE_SKIPLIST = [r'\\cli\\.*',
                 r'\\profiling\\.*',
                 r'\.blade\.php',
                 r'\\Console\\.*']
RE_FILE_SKIPLIST = []

PICKLE_FILE = 'dump.tmp'
OUTPUT_FILE = 'laravel_lite.php'
OUTPUT_FILE2 = 'laravel_lite_beautified.php'
declarations = {}


def compile_skiplists():
    for pattern in NAMESPACE_SKIPLIST:
        RE_NAMESPACE_SKIPLIST.append(re.compile(pattern))

    for pattern in FILE_SKIPLIST:
        RE_FILE_SKIPLIST.append(re.compile(pattern))


def append_file(namespace, declaration):
    #if namespace == '': namespace = ''
    global declarations
    if namespace not in declarations:
        declarations[namespace] = [declaration]
    else:
        declarations.get(namespace).append(declaration)


def minify_php(filename=None):
    return subprocess.Popen(['php', '-w', filename],
                            bufsize=1,
                            stdout=subprocess.PIPE,
                            shell=False).communicate()[0]


def get_filecontent(filename):
    return minify_php(filename)


def find_namespace(content):
    match = RE_NAMESPACE.search(content)
    if match:
        result = match.group(1)
    else:
        result = ''

    return result

SYMF_RMV = re.compile(r"""\s+('|")Symfony\\Component\\Console('|")\s*=>\s*path\(('|")sys('|")\)\s*\.\s*('|")vendor/Symfony/Component/Console('|"),""")
REQ_RMV = re.compile(r"""require\s+path\(['|"]sys['|"]\)\s*.\s*['|"]\w+['|"]\s*.\s*EXT;""")


def curate_content(content):
    content = content.replace('<?php', '')
    content = RE_NAMESPACE_OR_USAGE.sub('', content)
    return content.strip()


def find_namespace_usage(content):
    usages = []
    items = RE_NAMESPACE_USAGE.findall(content)
    for item in items:
        parts = item.split(',')
        for part in parts:
            usages.append(part.strip())
    return usages


def skip_file(filename):
    global RE_FILE_SKIPLIST
    for rex in RE_FILE_SKIPLIST:
        if rex.search(filename):
            return True
    return False


def skip_namespace(filename):
    global RE_NAMESPACE_SKIPLIST
    for rex in RE_NAMESPACE_SKIPLIST:
        if rex.search(filename):
            return True
    return False


def scan_file(filename, extension='.php'):
    '''
    Returns array of class, function, and member declarations for a given
    PHP source file.
    '''
    if skip_file(filename):
        return
    global declarations

    name, ext = os.path.splitext(filename)
    if ext == extension:
        content = get_filecontent(filename)

        declaration = {'filename': filename}
        declaration['namespace'] = '' if skip_namespace(filename) else find_namespace(content)
        declaration['namespace_usages'] = find_namespace_usage(content)

        if name.split('\\')[-1] == 'core':
            content = SYMF_RMV.sub('', content)
            content = REQ_RMV.sub('', content)

        declaration['code'] = curate_content(content)
        append_file(declaration['namespace'], declaration)


def scan_all_files(base_folder, extension='.php'):
    '''
    Returns array of class, function, and member declarations for all of the
    PHP source files on a given path.
    '''

    for root, dirs, files in os.walk(base_folder):
        for name in files:
            filename, ext = os.path.splitext(name)
            if ext == extension:
                path = os.path.join(root, name)
                #print('<< ' + name)
                scan_file(path)


def optimize_usages(namespace_entries):
    usages_totla = []
    for entry in namespace_entries:
        usages = entry['namespace_usages']
        usages_totla.extend(usages)
    return set(usages_totla)


def generate_namespace_code(usages, files):
    output = ''
    for usage in usages:
        output += 'use %s;\n' % (usage)

    for file_def in files:
        output += '/****    %s    ****/\n' % file_def['filename']
        output += file_def['code'] + '\n'
    return output


def generate_namespace_codeblock(namespace, usages, files):
    if namespace == '':
        return generate_namespace_code(usages, files)
    else:
        output = 'namespace %s {\n' % namespace
        output += generate_namespace_code(usages, files)
        output += '}\n'
        return output

compile_skiplists()
scan_all_files('laravel')
with open(PICKLE_FILE, 'wb') as f:
    pickle.dump(declarations, f, 1)

# with open(PICKLE_FILE, 'rb') as f:
#     data = pickle.load(f)
#     print json.dumps(data, indent=8)

with open(OUTPUT_FILE, 'wb') as f:
    header = '''<?php
/**
 * @package  Laravel Lite
 * @version  3.2.13
 */\n'''
    f.write(header)
    for (namespace, files) in declarations.items():
        usages = optimize_usages(files)
        f.write(generate_namespace_codeblock(namespace, usages, files))

cmd = "php_beautifier.bat" if platform == "win32" else "php_beautifier"
indent = "-t1"
filters = "Pear(add-header=false)"
fullinput = os.path.abspath(os.path.join(os.path.curdir, OUTPUT_FILE))
fulloutput = os.path.abspath(os.path.join(os.path.curdir, OUTPUT_FILE2))
p = subprocess.Popen([cmd, indent, "-l", filters, "-f", fullinput, "-o", fulloutput], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = p.communicate()
