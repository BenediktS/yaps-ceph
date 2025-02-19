#!/usr/bin/python3

# Copyright 2017 Kulturveranstaltungen des Bundes in Berlin GmbH
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.



import argparse
import json
import pprint
import subprocess
import sys

#
# try -h for info
# intended as an extended script sensor for paessler prtg
# transforming data from ceph -s 
# so install in /var/prtg/scriptsxml/ and check executable flag
# 
# assumes ceph access - check read permissions to ceph.conf
# 
# in prtg channel 'status' indicates 
# 0=OK 1=WARNING 2=ERROR
#



CEPH_BIN = '/usr/bin/ceph'

# max fill factor
CLUSTER_MAX_FILL = 2/3;

def _exec(args):
	cmd  = subprocess.Popen(args,
                       shell=False,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
	result = b''.join(cmd.stdout.readlines()).decode('utf8')
	if result == []:
		error = cmd.stderr.readlines()
		exit( "ERROR: %s" % error  )
	return result	

def main(sJson):
    j = json.loads(sJson)

    channels = []
    e = 0
    m = ''
    h = { 
        'HEALTH_OK' : 0, 'HEALTH_WARN' : 1, 'HEALTH_ERR' : 2 
    }[ j['health']['status'] ]
    e = max(e,h)


    # we see if we already learned about the situation and 
    # should raise the ceph warning to prtg err in next place
    unhandled = 0
    if e == 1:
        ws = j['health']['checks']
        unhandled = len(ws)
        for k,c in ws.items():
            if c['severity'] == 'HEALTH_WARN' : 
                unhandled -= 1
                m += c['summary']['message']+';'
        if unhandled==0:
            e = 0

    if e > 0:
        m += 'situation occured'
    channels.append( { 
        'channel' : 'status', 
        'value' : h,
        'LimitMode' : 1,
        'LimitMaxWarning' : 0.5,
        'LimitMaxError' : 1.5
    } )

    i = j['osdmap']['num_osds'] - j['osdmap']['num_up_osds']
    channels.append( {
        'channel' : 'missing_osds',
        'value' : i,
    } )

    channels.append( {
        'channel': 'bytes_used',
        'value':  j['pgmap'].get('bytes_used',0),
        'Unit': 'BytesDisk',
        'VolumeSize' : 'Tera'
    } )


    i = int( 
      j['pgmap'].get('bytes_total',0) * CLUSTER_MAX_FILL 
      - j['pgmap'].get('bytes_used',0)
    )
    channels.append( {
        'channel': 'bytes_avail',
        'value': i,
        'Unit': 'BytesDisk',
        'VolumeSize' : 'Tera'
    } )

    i = int( 
      ( j['pgmap'].get('bytes_used',0) / j['pgmap'].get('bytes_total',0)  ) * 100
    )
    channels.append( {
        'channel': 'used',
        'value': i,
	'Unit': 'Percent',
        'LimitMode' : 1,
        'LimitMaxWarning' : 80,
        'LimitMaxError' : 90
        
    } )



    for c in ['read_bytes_sec','write_bytes_sec']:
        channels.append( {
            'channel': c,
            'value': j['pgmap'].get(c,0),
            'Unit': 'BytesBandwidth',
            'SpeedSize' : 'Mega'	
        } )


    for c in ['read_op_per_sec','write_op_per_sec',
            'recovering_bytes_per_sec','recovering_objects_per_sec',
            'num_objects','misplaced_objects','degraded_objects'
        ]:
        channels.append( {
            'channel': c,
            'value': j['pgmap'].get(c,0)
        } )





    if not (args.json_file):
        j2 = json.loads(_exec([CEPH_BIN,'osd','df','--format=json']))
        maxUsed = 0
        maxUsedOSD = 0
	
        for osd in j2['nodes']:
            if osd['utilization'] > maxUsed:
                maxUsed = osd['utilization']
                maxUsedOSD = osd['id']

        channels.append( {
            'channel' : 'maxUsed',
            'Float' : 1,
            'DecimalMode' : 2,
            'value' : maxUsed,
            'Unit': 'Percent',
            'LimitMode' : 1,
            'LimitMaxWarning' : 80,
            'LimitMaxError' : 90
        } )

        channels.append( {
            'channel' : 'maxUsedOSD',
            'value' : maxUsedOSD
        } )


	
	
	

    print( json.dumps( {'prtg' : {
        'error' : e,
        'text' : m,
        'result' : channels
    } }) )
    
    return






argparserbase = argparse.ArgumentParser()
argparserbase.add_argument("--json-file", help="a file to parse instead of reading `ceph -s`")
args = argparserbase.parse_args()

if (args.json_file):
    with open(args.json_file,'r', encoding="utf8") as file: sJson = file.read()
else:
    sJson = _exec([CEPH_BIN,'-s','--format=json'])

main(sJson)


