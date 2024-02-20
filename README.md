# IOCLauncher

A simple dashboard to launch and keep track of command-line-launched services

# Purpose

To help manage the many microservices that make up our (EPICS) backends for the instrumentation, we need to launch several (micro)services called IOCs. These IOCs take care of communicating with the hardware device, and exposing the hardware parameters to the internal channel-access (CA) communications bus. 

Depending on the configuration of the machine, and depending on which pieces of hardware are attached, these could include more or fewer devices with their respective IOCs. We needed an easy way to keep track of, and launch new IOCs. A quick dashboard was built to provide this. The dashboard also shows a few graphs on which system resources can be tracked to aid troubleshooting. Logs showing STDOUT and STDERR can be displayed of running and ended/crashed IOCs, provided anything has been written to them. 

IOCs to be included in the interface can be configured in the associated YAML file, loaded on startup. The dashboard has been written using Python with Dash + Plotly

A Heartbeat is added as the first IOC, heartbeats are performed every two seconds, additional heartbeats can be triggered using the "check"-button. 

# Screenshots

![image](https://github.com/BAMresearch/IOCLauncher/assets/5449929/79fe5279-463f-479d-ad6a-dbfcdaf0ebd0)
