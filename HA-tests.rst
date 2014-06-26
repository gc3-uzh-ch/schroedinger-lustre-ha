HA tests
========

.. contents::

New tests,  26 June 2014
=========================

Stonith enabled.

Pacemaker configuration produced by `generator script make-lustre-crm-config.py <https://github.com/gc3-uzh-ch/schroedinger-lustre-ha/blob/master/make-lustre-crm-config.py>`__ (commit 8d5dfe8).


FC failures
-----------

lustre-mds2
"""""""""""

unlink FC on lustre-mds2: **behaviour as expected**
	- first FC, ok
	- second FC
		- resource (mgt) migrates correctly, node was fenced (power off)
	
power on lustre-mds2, without FC (because sysadmin forgot to plug FC cables)
	- we run `crm resource migrate mgt lustre-mds2` (FC still unplugged)
		- lustre-mds2 was fenced off again (unconsciously unexpected, but correct behaviour)
	- FC plugged in, power on server
		- resource are not migrated back automatically
		- `crm resource migrate mgt lustre-mds2` success to migrate back


lustre-oss5
"""""""""""

unlink FC on lustre-oss5: **behaviour as expected**
	- first FC, ok, multipath acks missing path
	- second FC, multipath acks no path to volume
	- kernel says no I/O possible on device
	- pacemaker primitive filesystem acknowledge impossible to do I/O on device
	- node was fenced
	- target moved to partner node lustre-oss6

	
stonith-lustre-oss5 was running on lustre-oss6, but decision to fence oss5 came from lustre-oss2 (crmd.3533@lustre-oss2.ften.es.hpcn.uzh.ch.7d782a67 on the following log)

::

	==> /var/log/messages <==
	Jun 26 16:16:41 lustre-mds1 pacemakerd[3248]:   notice: crm_update_peer_state: pcmk_quorum_notification: Node lustre-oss5.ften.es.hpcn.uzh.ch[176250134] - sta
	te is now lost (was member)
	Jun 26 16:16:41 lustre-mds1 stonith-ng[3251]:   notice: remote_op_done: Operation poweroff of lustre-oss5.ften.es.hpcn.uzh.ch by lustre-oss6.ften.es.hpcn.uzh.
	ch for crmd.3533@lustre-oss2.ften.es.hpcn.uzh.ch.7d782a67: OK
	Jun 26 16:16:41 lustre-mds1 crmd[3255]:   notice: tengine_stonith_notify: Peer lustre-oss5.ften.es.hpcn.uzh.ch was terminated (poweroff) by lustre-oss6.ften.e
	s.hpcn.uzh.ch for lustre-oss2.ften.es.hpcn.uzh.ch: OK (ref=7d782a67-1528-4d74-b2ff-02cfe8a37102) by client crmd.3533
	Jun 26 16:16:45 lustre-mds1 attrd[3253]:   notice: attrd_peer_message: Processing sync-response from lustre-oss3.ften.es.hpcn.uzh.ch
	Jun 26 16:17:32 lustre-mds1 kernel: Lustre: lustre-OST001a-osc-MDT0000: Connection restored to lustre-OST001a (at 10.130.93.23@o2ib)
	Jun 26 16:18:25 lustre-mds1 kernel: Lustre: lustre-OST0012-osc-MDT0000: Connection restored to lustre-OST0012 (at 10.130.93.23@o2ib)
	Jun 26 16:18:55 lustre-mds1 kernel: Lustre: lustre-OST000a-osc-MDT0000: Connection restored to lustre-OST000a (at 10.130.93.23@o2ib)
	Jun 26 16:19:40 lustre-mds1 kernel: Lustre: lustre-OST0002-osc-MDT0000: Connection restored to lustre-OST0002 (at 10.130.93.23@o2ib)


power on lustre-oss5, with a single FC plugged in
	- resources are not migrated back
	- `crm resource migrate ost{2,10,18,26} lustre-oss5` success to migrate back
	

InfiniBand
----------

lustre-oss5
"""""""""""

unplug InfiniBand cable: **behaviour as expected**
	- ethmonitor acknowledge failure
	- resource are migrated to failover partner
	- node is NOT fenced
	
ethernet
--------

lustre-oss6
"""""""""""

Unplug ethernet cable: **behaviour as expected**
	- ethmonitor acknowledge failure
	- stonith primitive migrates from lustre-oss5 to lustre-mds2
	- apart stonith primitive, nothing was fenced nor moved


Reboot
------


lustre-oss5
"""""""""""

During normal condition, just run `reboot` on a server: **server fails a clean reboot**
	- resources are migrated to failover partner oss6
	- oss5 hangs during shutdown
		- maybe InfiniBand modules are unloaded before lnet (lustre networking module)
		
Open points
-----------

- We get rid of MailTo primitives, need to substitute them with something more informative.
- Why a server fails a normal reboot procedure?


Schroedinger maintenance, 25 june 2014
======================================

Since
- STONITH was disabled so far
- `ping` primitive was not working properly
- we need to test if the following Infiniband ethmonitor timeout is working properly
	- short answer: no, I think timeout should be less than interval * repeat_count, where the default for repeat_count is 5

	::
	
		primitive ib0_up ethmonitor \
				params interface=ib0 name=ib0_up \
				op monitor interval=5s timeout=60s \
				   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
				op start interval=0 timeout=60s \
				op stop interval=0	


I propose to re-do all the tests we did during last maintenance.

TO-DO tests
^^^^^^^^^^^


Goal of the tests is:
	- verify STONITH is working well
	- verify ethmonitor on InfiniBand is working well (timeout issue)
	- verify the expected behaviour when a node experiments a failure

**Expected behaviour**: *resources (Lustre target) are migrated correctly on partner node. After re-connecting the cable, the resource is NOT migrated back automatically*.
	

To accomplish this we need:

	to enable STONITH
		- crm configure property stonith-enabled=true
		- when STONITH is enabled, the default behaviour for a failing Pacemaker resource is fencing
	if needed, modify the timeout value in the ethmonitor resource
		- we need a timeout smaller than interval*repeat_count
		- for instance ("...op monitor interval=10s timeout=50s...")



Single host failures
""""""""""""""""""""


- Fibre Channel:

  1. unlink first cable:

     - Expected:

       - nothing must happen, multipath acknowledges the missing path

  2. unlink second cable:

     - multipath acknowledges no path to volume
     - filesystem primitive acknowledges impossible I/O on disk (thanks to CHECK_OCF_LEVEL=10)
     - filesystem primitive fails
     - failing node is fenced (power off)
     - Pacemaker migrates Lustre target

		
- Infiniband:

  - unlink cable:

    Expected:

     - ethmonitor acknowledges missing link (before ping primitive)
     - ethmonitor fails
     - failing node is fenced (power off)
     - Pacemaker migrates Lustre target
		
  - disable IB port test (`ibportstate ... 1 disable`)?

    **OK:** 

    - disabled `lustre-oss1` IB port with `ibportstate ... disable` (from another host)
    - pacemaker reacts and migrates all OSTs to `lustre-oss2`
    - **note:** node is *not* fenced off

    Example output from the logs on `lustre-oss1`::

      Jun 25 23:57:07 lustre-oss1 corosync[2981]:   [TOTEM ] Marking ringid 1 interface 10.130.93.14 FAULTY
      Jun 25 23:57:09 lustre-oss1 ethmonitor(ib0_up)[7888]: WARNING: Monitoring of ib0_up failed, 2 retries left.
      Jun 25 23:57:19 lustre-oss1 ethmonitor(ib0_up)[7888]: WARNING: Monitoring of ib0_up failed, 1 retries left.
      Jun 25 23:57:23 lustre-oss1 crmd[14999]:   notice: do_state_transition: State transition S_IDLE -> S_POLICY_ENGINE [ input=I_PE_CALC cause=C_FSA_INTERNAL origin=abort_transition_graph ]
      Jun 25 23:57:24 lustre-oss1 kernel: Lustre: 8465:0:(client.c:1868:ptlrpc_expire_one_request()) @@@ Request sent has timed out for sent delay: [sent 1403733437/real 0]  req@ffff88103b8d9800 x1471890494345888/t0(0) o400->lustre-MDT0000-lwp-OST0018@10.130.93.10@o2ib:12/10 lens 224/224 e 0 to 1 dl 1403733444 ref 2 fl Rpc:XN/0/ffffffff rc 0/-1
      Jun 25 23:57:24 lustre-oss1 kernel: Lustre: lustre-MDT0000-lwp-OST0018: Connection to lustre-MDT0000 (at 10.130.93.10@o2ib) was lost; in progress operations using this service will wait for recovery to complete
      Jun 25 23:57:24 lustre-oss1 kernel: Lustre: Skipped 1 previous similar message
      Jun 25 23:57:24 lustre-oss1 kernel: LustreError: 166-1: MGC10.130.93.11@o2ib: Connection to MGS (at 10.130.93.10@o2ib) was lost; in progress operations using this service will fail
      Jun 25 23:57:24 lustre-oss1 pengine[3549]:   notice: LogActions: Move    ost00#011(Started lustre-oss1.ften.es.hpcn.uzh.ch -> lustre-oss2.ften.es.hpcn.uzh.ch)
      Jun 25 23:57:24 lustre-oss1 pengine[3549]:   notice: LogActions: Move    ost08#011(Started lustre-oss1.ften.es.hpcn.uzh.ch -> lustre-oss2.ften.es.hpcn.uzh.ch)
      Jun 25 23:57:24 lustre-oss1 pengine[3549]:   notice: LogActions: Move    ost16#011(Started lustre-oss1.ften.es.hpcn.uzh.ch -> lustre-oss2.ften.es.hpcn.uzh.ch)
      Jun 25 23:57:24 lustre-oss1 pengine[3549]:   notice: LogActions: Move    ost24#011(Started lustre-oss1.ften.es.hpcn.uzh.ch -> lustre-oss2.ften.es.hpcn.uzh.ch)
      Jun 25 23:57:24 lustre-oss1 pengine[3549]:   notice: process_pe_message: Calculated Transition 28: /var/lib/pacemaker/pengine/pe-input-152.bz2
      Jun 25 23:57:24 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 87: stop ost00_stop_0 on lustre-oss1.ften.es.hpcn.uzh.ch (local)
      Jun 25 23:57:24 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 104: stop ost08_stop_0 on lustre-oss1.ften.es.hpcn.uzh.ch (local)
      Jun 25 23:57:24 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 121: stop ost16_stop_0 on lustre-oss1.ften.es.hpcn.uzh.ch (local)
      Jun 25 23:57:24 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 138: stop ost24_stop_0 on lustre-oss1.ften.es.hpcn.uzh.ch (local)
      Jun 25 23:57:24 lustre-oss1 Filesystem(ost24)[8135]: INFO: Running stop for /dev/mapper/ost24 on /srv/lustre/ost/24
      Jun 25 23:57:24 lustre-oss1 Filesystem(ost00)[8132]: INFO: Running stop for /dev/mapper/ost00 on /srv/lustre/ost/0
      Jun 25 23:57:24 lustre-oss1 Filesystem(ost16)[8134]: INFO: Running stop for /dev/mapper/ost16 on /srv/lustre/ost/16
      Jun 25 23:57:24 lustre-oss1 Filesystem(ost08)[8133]: INFO: Running stop for /dev/mapper/ost08 on /srv/lustre/ost/8
      Jun 25 23:57:24 lustre-oss1 Filesystem(ost24)[8135]: INFO: Trying to unmount /srv/lustre/ost/24
      Jun 25 23:57:24 lustre-oss1 kernel: Lustre: Failing over lustre-OST0018
      Jun 25 23:57:24 lustre-oss1 kernel: Lustre: Skipped 3 previous similar messages
      Jun 25 23:57:24 lustre-oss1 Filesystem(ost00)[8132]: INFO: Trying to unmount /srv/lustre/ost/0
      Jun 25 23:57:24 lustre-oss1 Filesystem(ost16)[8134]: INFO: Trying to unmount /srv/lustre/ost/16
      Jun 25 23:57:24 lustre-oss1 Filesystem(ost08)[8133]: INFO: Trying to unmount /srv/lustre/ost/8
      Jun 25 23:57:24 lustre-oss1 kernel: Lustre: Failing over lustre-OST0000
      Jun 25 23:57:24 lustre-oss1 kernel: Lustre: server umount lustre-OST0008 complete
      Jun 25 23:57:24 lustre-oss1 kernel: Lustre: Skipped 2 previous similar messages
      Jun 25 23:57:24 lustre-oss1 Filesystem(ost24)[8135]: INFO: unmounted /srv/lustre/ost/24 successfully
      Jun 25 23:57:25 lustre-oss1 Filesystem(ost08)[8133]: INFO: unmounted /srv/lustre/ost/8 successfully
      Jun 25 23:57:25 lustre-oss1 crmd[14999]:   notice: process_lrm_event: Operation ost24_stop_0: ok (node=lustre-oss1.ften.es.hpcn.uzh.ch, call=1122, rc=0, cib-update=605, confirmed=true)
      Jun 25 23:57:25 lustre-oss1 Filesystem(ost00)[8132]: INFO: unmounted /srv/lustre/ost/0 successfully
      Jun 25 23:57:25 lustre-oss1 crmd[14999]:   notice: process_lrm_event: Operation ost08_stop_0: ok (node=lustre-oss1.ften.es.hpcn.uzh.ch, call=1118, rc=0, cib-update=606, confirmed=true)
      Jun 25 23:57:25 lustre-oss1 crmd[14999]:   notice: process_lrm_event: Operation ost00_stop_0: ok (node=lustre-oss1.ften.es.hpcn.uzh.ch, call=1116, rc=0, cib-update=607, confirmed=true)
      Jun 25 23:57:25 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 139: start ost24_start_0 on lustre-oss2.ften.es.hpcn.uzh.ch
      Jun 25 23:57:25 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 140: monitor ost24_monitor_120000 on lustre-oss2.ften.es.hpcn.uzh.ch
      Jun 25 23:57:29 lustre-oss1 ethmonitor(ib0_up)[7888]: ERROR: Monitoring of ib0_up failed.
      Jun 25 23:57:29 lustre-oss1 crmd[14999]:   notice: abort_transition_graph: Transition aborted by status-176250126-ib0_up, ib0_up=0: Transient attribute change (modify cib=0.202.840, source=te_update_diff:389, path=/cib/status/node_state[@id='176250126']/transient_attributes[@id='176250126']/instance_attributes[@id='status-176250126']/nvpair[@id='status-176250126-ib0_up'], 0)
      Jun 25 23:57:30 lustre-oss1 kernel: Lustre: server umount lustre-OST0010 complete
      Jun 25 23:57:30 lustre-oss1 Filesystem(ost16)[8134]: INFO: unmounted /srv/lustre/ost/16 successfully
      Jun 25 23:57:30 lustre-oss1 crmd[14999]:   notice: process_lrm_event: Operation ost16_stop_0: ok (node=lustre-oss1.ften.es.hpcn.uzh.ch, call=1120, rc=0, cib-update=608, confirmed=true)
      Jun 25 23:57:30 lustre-oss1 crmd[14999]:   notice: run_graph: Transition 28 (Complete=6, Pending=0, Fired=0, Skipped=7, Incomplete=0, Source=/var/lib/pacemaker/pengine/pe-input-152.bz2): Stopped
      Jun 25 23:57:30 lustre-oss1 pengine[3549]:   notice: LogActions: Start   ost00#011(lustre-oss2.ften.es.hpcn.uzh.ch)
      Jun 25 23:57:30 lustre-oss1 pengine[3549]:   notice: LogActions: Start   ost08#011(lustre-oss2.ften.es.hpcn.uzh.ch)
      Jun 25 23:57:30 lustre-oss1 pengine[3549]:   notice: LogActions: Start   ost16#011(lustre-oss2.ften.es.hpcn.uzh.ch)
      Jun 25 23:57:30 lustre-oss1 pengine[3549]:   notice: process_pe_message: Calculated Transition 29: /var/lib/pacemaker/pengine/pe-input-153.bz2
      Jun 25 23:57:30 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 116: start ost16_start_0 on lustre-oss2.ften.es.hpcn.uzh.ch
      Jun 25 23:57:31 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 100: start ost08_start_0 on lustre-oss2.ften.es.hpcn.uzh.ch
      Jun 25 23:57:31 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 117: monitor ost16_monitor_120000 on lustre-oss2.ften.es.hpcn.uzh.ch
      Jun 25 23:57:31 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 84: start ost00_start_0 on lustre-oss2.ften.es.hpcn.uzh.ch
      Jun 25 23:57:31 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 101: monitor ost08_monitor_120000 on lustre-oss2.ften.es.hpcn.uzh.ch
      Jun 25 23:57:32 lustre-oss1 crmd[14999]:   notice: te_rsc_command: Initiating action 85: monitor ost00_monitor_120000 on lustre-oss2.ften.es.hpcn.uzh.ch
      Jun 25 23:57:32 lustre-oss1 crmd[14999]:   notice: run_graph: Transition 29 (Complete=6, Pending=0, Fired=0, Skipped=0, Incomplete=0, Source=/var/lib/pacemaker/pengine/pe-input-153.bz2): Complete
      Jun 25 23:57:32 lustre-oss1 crmd[14999]:   notice: do_state_transition: State transition S_TRANSITION_ENGINE -> S_IDLE [ input=I_TE_SUCCESS cause=C_FSA_INTERNAL origin=notify_crmd ]

		
- Ethernet `eth0`

  - unlink cable:

    - Expected:
		
      - Pacemaker must continue operations thanks to redundant rings
      - STONITH resource cannot operate, so will fail?
      - node will be fenced? we don't need fence here.. just move resources? to avoid this behaviour, we need to modify the default for the stop operation (no "on-fail=fence")

  - disable interface (*ifdown eth0*):

    **OK:** 
    - Pacemaker migrates STONITH resources to another host
    - Corosync marks the interface as FAULTY
    - No other visible effect

    Excerpt from the relevant logs:

        Jun 26 00:07:09 lustre-oss4 ntpd[3255]: Deleting interface #3 eth0, 10.129.93.19#123, interface stats: received=202, sent=202, dropped=0, active_time=31134 secs
        Jun 26 00:07:09 lustre-oss4 ntpd[3255]: 10.129.80.60 interface 10.129.93.19 -> (none)
        Jun 26 00:07:09 lustre-oss4 ntpd[3255]: 10.129.80.52 interface 10.129.93.19 -> (none)
        Jun 26 00:07:09 lustre-oss4 ntpd[3255]: 10.129.80.50 interface 10.129.93.19 -> (none)
        Jun 26 00:07:09 lustre-oss4 ntpd[3255]: peers refreshed
        Jun 26 00:07:09 lustre-oss4 corosync[2973]:   [TOTEM ] sendmsg(ucast) failed (non-critical): Invalid argument (22)
        ...
        Jun 26 00:07:10 lustre-oss4 corosync[2973]:   [TOTEM ] sendmsg(ucast) failed (non-critical): Invalid argument (22)
        Jun 26 00:07:10 lustre-oss4 corosync[2973]:   [TOTEM ] Marking ringid 0 interface 10.129.93.19 FAULTY
        Jun 26 00:07:11 lustre-oss4 ethmonitor(ipmi_net_up)[24209]: WARNING: Monitoring of ipmi_net_up failed, 2 retries left.
        Jun 26 00:07:11 lustre-oss4 corosync[2973]:   [TOTEM ] sendmsg(ucast) failed (non-critical): Invalid argument (22)
        ...
        Jun 26 00:07:15 lustre-oss4 ethmonitor(ipmi_net_up)[24209]: WARNING: Monitoring of ipmi_net_up failed, 1 retries left.
        Jun 26 00:07:15 lustre-oss4 stonith-ng[3552]:   notice: log_operation: Operation 'monitor' [25036] for device 'stonith-lustre-oss3' returned: -201 (Generic Pacemaker error)
        Jun 26 00:07:15 lustre-oss4 stonith-ng[3552]:  warning: log_operation: stonith-lustre-oss3:25036 [ Getting status of IPMI:10.128.93.18...Spawning: '/usr/bin/ipmitool -I lanplus -H '10.128.93.18' -U 'ADMIN' -P '[set]' -v chassis power status'... ]
        Jun 26 00:07:15 lustre-oss4 stonith-ng[3552]:  warning: log_operation: stonith-lustre-oss3:25036 [ Failed ]
        Jun 26 00:07:15 lustre-oss4 crmd[3556]:    error: process_lrm_event: Operation stonith-lustre-oss3_monitor_60000 (node=lustre-oss4.ften.es.hpcn.uzh.ch, call=1092, status=4, cib-update=688, confirmed=false) Error
        Jun 26 00:07:15 lustre-oss4 corosync[2973]:   [TOTEM ] sendmsg(ucast) failed (non-critical): Invalid argument (22)
        Jun 26 00:07:16 lustre-oss4 crmd[3556]:   notice: process_lrm_event: Operation stonith-lustre-oss3_stop_0: ok (node=lustre-oss4.ften.es.hpcn.uzh.ch, call=1105, rc=0, cib-update=689, confirmed=true)
        Jun 26 00:07:16 lustre-oss4 corosync[2973]:   [TOTEM ] sendmsg(ucast) failed (non-critical): Invalid argument (22)
        ...
        Jun 26 00:07:24 lustre-oss4 corosync[2973]:   [TOTEM ] sendmsg(ucast) failed (non-critical): Invalid argument (22)
        Jun 26 00:07:25 lustre-oss4 ethmonitor(ipmi_net_up)[24209]: ERROR: Monitoring of ipmi_net_up failed.


- IPMI ethernet `eth0.617`

  - disable interface (*ifdown eth0.617*):

    **OK:** 

    - Pacemaker migrates STONITH resources to another host.
    - No other visible effect


Tests already performed
=======================

Expected behaviour definition: *resources are migrated correctly on pair node. After re-connecting the cable, the resource is NOT migrated back automatically*.

Single host failures
--------------------

- FC (lustre-mds2, mgt target)
	- unlink first cable
		- behaviour: as expected
	- unlink second one
		- behaviour: as expected.


- IB (lustre-oss2)

    - unlink cable
        - behaviour: as expected.

    - disable IB port
        - behaviour: as expected.

    - block ICMP
        - behaviour ? > RM: I think this test can be safely skipped!

        
- oss2 ethernet (do we have another interface available on hosts, and ports on switch?)
    - unlink cable
      - Apparently, this cause corosync communication to stop (even
        though they should talk on the IB channel), and all resources
        to be blocked. resources are stopped on the "dead" node, but
        not migrated to other resources.
      - replacing the cable, something strange happens: resources are
        first mounted on oss1 (the pair resource), and *then* migrated
        to oss2 (the "dead" node) . Misbehaviour may be related to the ``ibportstate`` command.
        
- ethernet (lustre-mds2)
    - unlink cable
      - ping fails because the machine cannot resolve ib* hostnames,
        and mgt is moved to lustre-mds1.
    - expected behaviour: the resource should not migrate due to the presence of the second communication ring (if the ping resource is working).


Multiple hosts failure
----------------------

> RM: In both these cases, I think the Lustre storage cluster should
> be down.  At any rate, these are failure modes that cannot be served
> by our current HW configuration!

- what if both the mds are down?
    - do we need another check on pacemaker?

- what about the quorum? if 5 hosts are down?
    - behaviour? 



Open points
-----------

* STONITH is still disabled on all servers

* eth1 on servers is not used. We could:
	- bond it with eth0 (do we have another port on switch?)
	- link it to the IPMI LAN?

* What if eth0.617 is not available?

* InfiniBand behaviour	
	- ethmonitor timeout
		- looking at ``crm ra info ocf:heartbeat:ethmonitor``, the timeout should be `at least repeat_interval \* repeatcount`. But the default is 20 seconds.
	- when InfiniBand is missing, do we want a failover caused by failure of ping or ethmonitor resource?
		- adjust timeout as needed
	- when InfiniBand is missing, what behaviour do we expect?
		- do we need fencing?
		
* Quorum: we have ten nodes in the HA cluster
	- at least N/2+1 nodes are needed to have quorum
	- when 5 nodes can't vote, what's happening?
	
* What if both the MDS servers are missing?
	- since we have a Mandatory orded (``order mdt_after_mgt Mandatory: mgt mdt``), a missing mgt should actually lead every Lustre target down

* Why the ``interleave`` meta attribute in the ethmonitor clone for InfiniBand check?
	- the interleave is needed `only when a master/slave set is configured <http://www.hastexo.com/resources/hints-and-kinks/interleaving-pacemaker-clones>`__
	

* Ping is failing when eth0 is missing (and then resource will migrate)
	- change hostnames with ip addresses?
	- name resolution handling
	
No failures (maintenance use cases)
-----------------------------------

- Set the HA cluster in *maintenance-mode*
	``crm configure property maintenance-mode=true``

- Tell CRM to migrate services (expect: services migrate)
	use ``crm resource migrate [resource-name] [FQDN]`` to move the resource TO the FQDN.

- Clean shutdown of a host (expect: services migrate)
	I would not perform a node shutdown with Pacemaker running on that node. I would migrate the services, and then cleanly shut down the node.
	If for any reason a node fails to move target to its partner, this last one will fence the node.

- Stop CRM on node (expect: services migrate)
	CRM is not a daemon: is the shell you use to interact with Pacemaker. You could stop ``corosync`` or ``pacemaker``.

	
	
Tests on lustre-test{1,2}
-------------------------

test HA
	- unlink first SAS, ok
	- unlink second SAS
		- fail of filesystem monitoring
		- trying to stop target on failing node
		- timeout on stop operation -> FENCING
	
	- when machine reboots, still SAS unlinked
		- node resources unmounted
		- trying to start target
		
		
	- ib test
		- physically unlink ib0
			- migration OK
			- failback OK when relink
		- ifdown ib0
			- migration OK
			- failback OK when ifup
		- why no stonith?
			- timeout need to be less then repeat_count * repeat_interval ?


