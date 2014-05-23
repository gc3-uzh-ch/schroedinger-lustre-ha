#! /usr/bin/env python
"""
Generate the `crm configure` commands for setting up Lustre HA
on the UZH Schroedinger cluster.

Load the output of this script with `crm configure -f`.
"""

## imports

from itertools import izip, chain, cycle, repeat


## CONFIGURATION

RESOURCES = {
    # name -> { params }
    'mgt': {
            'device':     '/dev/mapper/vol_mgt',
            'mountpoint': '/srv/lustre/mgt',
            'primary':    'lustre-mds2',
            'secondary':  'lustre-mds1',
        },
    'mdt': {
            'device':     '/dev/mapper/vol_mdt',
            'mountpoint': '/srv/lustre/mdt',
            'primary':    'lustre-mds1',
            'secondary':  'lustre-mds2',
        },
}
# OSTs are placed on OSS pairs in a round-robin fashion:
# - OST0 is on OSS1 and OSS2;
# - OST1 is on OSS3 and OSS4;
# ...
# - OST3 is on OSS7 and OSS8;
# - OST4 is on OSS2 and OSS1 (swapped);
# ...
# - OST7 is on OSS8 and OSS7 (swapped);
# - OST8 is on OSS1 and OSS2;
# ...
for n, primary, secondary, swap in izip(
        range(0,32),                  # 0,1,2,3,4,... (-> n)
        cycle(range(1,9,2)),          # 1,3,5,7,1,... (-> primary)
        cycle(range(2,9,2)),          # 2,4,6,8,2,... (-> secondary)
        cycle([False]*4 + [True]*4)): # F,F,F,F,T,... (-> swap)
    if swap:
        primary, secondary = secondary, primary
    RESOURCES['ost%02d' % n] = {
        'device':     ('/dev/mapper/ost%02d' % n),
        'mountpoint': ('/srv/lustre/ost/%d' % n),
        'primary':    ('lustre-oss%d' % primary),
        'secondary':  ('lustre-oss%d' % secondary),
    }


## print CRM commands

OSS_NODES = set([ params['primary'] for params in RESOURCES.itervalues() if 'oss' in params['primary'] ])
MDS_NODES = set([ params['primary'] for params in RESOURCES.itervalues() if 'oss' not in params['primary'] ])

ALL_NODES = set.union(MDS_NODES, OSS_NODES)

# insert a backreference into every "params" part,
# to simplify code below
for name, params in RESOURCES.iteritems():
    params['name'] = name

# define nodes
# this is not needed, since pacemaker will auto-populate with node names
#for node in ALL_NODES:
#    print("node %s.ften.es.hpcn.uzh.ch" % node)

# set global defaults
print("""
#
# Set default resource "stickiness",
# so that Lustre targets won't move
# to another server unless there is
# a sysadmin watching.
#
rsc_defaults rsc-options: \\
        resource-stickiness=2000
""")

# set up STONITH
print("""
#
# For each host, define how we STONITH that host.
#
""")
for node in ALL_NODES:
    print(r"""
primitive stonith-%(node)s stonith:fence_ipmilan \
  params \
    pcmk_host_list=%(node)s pcmk_host_check=static-list \
    ipaddr="sc%(node)s.mngt.es.hpcn.uzh.ch" \
    login=root passwd_script="/var/lib/pacemaker/ipmi_passwd.sh" \
    verbose=true lanplus=true action=off \
    op monitor interval=60s
""" % dict(node=node))

print("""
#
# Hosts are organized in pairs; for each node, constrain the STONITH services to run on the peer node
#
""")
pairs = set()
for name, params in RESOURCES.iteritems():
    pair = frozenset([ params['primary'], params['secondary'] ])
    pairs.add(pair)
def configure_stonith_location(target, killer):
    "Configure location contraints so that host `target` is STONITH'd by host `killer`"
    location = ("location locate-stonith-%(target)s stonith-%(target)s \\" + '\n') % locals()
    for node in ALL_NODES:
        if node == killer:
            location += ("  rule $id=stonith-%(target)s-on-%(killer)s 1000: #uname eq %(killer)s.ften.es.hpcn.uzh.ch \\" + '\n') % locals()
        else:
            location += ("  rule $id=stonith-%(target)s-not-on-%(node)s -INFINITY: #uname eq %(node)s.ften.es.hpcn.uzh.ch \\" + '\n') % locals()
    return location[:-2]+'\n'
for pair in pairs:
    one, other = pair
    print (configure_stonith_location(one, other) + '\n')
    print (configure_stonith_location(other, one) + '\n')

print(r"""
#
# check that the `ib0` interface is up
#
primitive ib0_up ethmonitor \
  params interface=ib0 name=ib0_up \
  op monitor interval=5s timeout=60s \
  op start interval=0 timeout=60s \
  op stop interval=0

clone ib0_up_clone ib0_up \
  meta globally-unique=false ordered=false notify=false interleave=true clone-node-max=1
""")

print(r"""
#
# check IB connectivity towards other nodes:
# the MDSes and a few compute nodes (one per
# rack and chassis); this makes a total of 26
# pinged nodes
#
primitive ping ocf:pacemaker:ping \
    params name=ping dampen=5s multiplier=10 host_list="%s" \
    op start timeout=120 \
    op monitor timeout=60 interval=10 \
    op stop timeout=20

clone ping_clone ping \
    meta globally-unique=false clone-node-max=1
    """ % str.join(' ', [('ib%s' % name)
        for name in set.union(MDS_NODES, set([
            # ((rack+chassis) % p) seems to give a good distribution of values mod p
            ('r%02dc%02db%02dn%02d' % (rack, chassis, 1+((rack+chassis) % 12), 1 + ((rack+chassis) % 2)))
            for rack in [1,2,3,6,7,8]
            for chassis in [1,2,3,4]
    ]))]))

# define filesystems
for name, params in sorted(RESOURCES.items()):
    print(r"""
#
# The `Filesystem` RA checks that a device is readable
# and that a filesystem is mounted. We use it to manage
# the Lustre OSTs.
#
primitive %(name)s-ldiskfs ocf:heartbeat:Filesystem \
  params device="%(device)s" directory="%(mountpoint)s" fstype="lustre" \
  operations $id="%(name)s-operations" \
  op monitor interval=120 timeout=60 OCF_CHECK_LEVEL=10 \
  op start   interval=0   timeout=300 \
  op stop    interval=0   timeout=300
""" % params)

# resource location
print("""
#
# Bind OST locations to hosts that can actually support them.
#
""")
for name, params in sorted(RESOURCES.items()):
    location_rule = ('location %(name)s-location %(name)s-ldiskfs \\' + '\n') % params
    for node in ALL_NODES:
        params['node'] = node
        params['role'] = node[len('lustre-'):]
        if node == params['primary']:
            location_rule += ('  rule $id="%(name)s_primary_on_%(role)s" 1000: #uname eq %(node)s.ften.es.hpcn.uzh.ch \\' + '\n') % params
        elif node == params['secondary']:
            location_rule += ('  rule $id="%(name)s_secondary_on_%(role)s" 100: #uname eq %(node)s.ften.es.hpcn.uzh.ch \\' + '\n') % params
        else:
            location_rule += ('  rule $id="%(name)s_not_on_%(role)s" -INFINITY: #uname eq %(node)s.ften.es.hpcn.uzh.ch \\' + '\n') % params
    location_rule += ('  rule $id="%(name)s_only_if_ping_works" -INFINITY: not_defined ping or ping number:lte 0\n') % params
    print(location_rule)

# ensure co-location and start/stop ordering
for name, params in sorted(RESOURCES.items()):
    print("""colocation %(name)s-with-ib INFINITY: %(name)s-ldiskfs ib0_up_clone""" % params)
    print("""order %(name)s-after-ib0-up Mandatory: ib0_up_clone %(name)s-ldiskfs""" % params)

# mouting Lustre targets must be serialized on a single host
print("""
#
# Serialize mounting of Lustre targets,
# see: https://jira.hpdd.intel.com/browse/LU-1279
#
""")
targets_by_node_pair = { }
for name, params in RESOURCES.items():
    pair = frozenset([ params['primary'], params['secondary'] ])
    if pair in targets_by_node_pair:
        targets_by_node_pair[pair].append('%(name)s-ldiskfs' % params)
    else:
        targets_by_node_pair[pair] = [ ('%(name)s-ldiskfs' % params) ]
for pair, targets in sorted(targets_by_node_pair.items()):
    if len(targets) > 1:
        print("""order serialize_targets_on_%s Serialize: %s"""
              % (str.join('-and-', sorted(pair)),
                 str.join(' ', reversed(sorted(targets)))))

# Lustre requires some global start/stop ordering
print("""
order mdt_after_mgt Mandatory: mgt-ldiskfs mdt-ldiskfs
""" % ())
for name, params in sorted(RESOURCES.items()):
    if name not in ['mdt', 'mgt']:
        print("order %(name)s_after_mdt Mandatory: mdt-ldiskfs %(name)s-ldiskfs" % params)

# ensure STONITH is enabled
print ("""
property cib-bootstrap-options: \\
        stonith-enabled=false \\
        stonith-action=poweroff \\
        maintenance-mode=true
""")


# load configuration
#print ("""
#commit
#""")
