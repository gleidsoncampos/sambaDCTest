#yaml tests

from __future__ import print_function
import yaml
import paramiko
import sys
from sambaDcTestsCommands import sambaDcTestsCommands

cfg_login ={}
cfg_task ={}
yamlFile = sys.argv[1:].__str__().strip("[']")
print (yamlFile)

for key, value in yaml.load(open(yamlFile))['credentials'].iteritems():
    cfg_login[key]=value
print (cfg_login.get('dcsIPList'))
print (cfg_login.get('dcsNameList'))

