# Validation

This plugin provides OpenStack Integration Test Suite: tempest for Sunbeam. It is based on [tempest-k8s](https://opendev.org/openstack/sunbeam-charms/src/branch/main/charms/tempest-k8s) and [tempest-rock](https://github.com/canonical/ubuntu-openstack-rocks/tree/main/rocks/tempest) project.

## Installation

To enable cloud validation, you need an already bootstrapped Sunbeam instance. Then, you can install the plugin with:

```bash
sunbeam enable validation
```

This plugin is also related to `observability` plugin.

## Contents

This plugin will install [tempest-k8s](https://opendev.org/openstack/sunbeam-charms/src/branch/main/charms/tempest-k8s), and provide command line interface: `sunbeam validate`, `sunbeam validation-lists`, and `sunbeam configure validation` (disabled) to your Sunbeam deployment.

Additionally, if you enable `observability` plugin, you will also get periodic cloud validation feature from this plugin. You can configure the periodic validation schedule using `sunbeam configure validation`. The periodic cloud validation results can be seen in the Grafana dashboard.

## Removal

To remove the plugin, run:

```bash
sunbeam disable validation
```
