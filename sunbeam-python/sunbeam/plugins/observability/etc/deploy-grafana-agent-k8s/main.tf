# Terraform manifest for deployment of Grafana Agent
#
# Copyright (c) 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

terraform {
  required_providers {
    juju = {
      source  = "juju/juju"
      version = "= 0.10.1"
    }
  }
}

data "terraform_remote_state" "cos" {
  backend = var.cos-state-backend
  config  = var.cos-state-config
}

resource "juju_application" "grafana-agent-k8s" {
  name  = "grafana-agent-k8s"
  model = var.model

  # note that we need to make sure the "base" matches the environment we are
  # deploying.
  charm {
    name     = "grafana-agent-k8s"
    base     = "ubuntu@22.04"
    channel  = var.grafana-agent-k8s-channel
    revision = var.grafana-agent-k8s-revision
  }

  units  = 1
  config = var.grafana-agent-k8s-config
}

# juju integrate grafana-agent-k8s:send-remote-write cos.prometheus-receive-remote-write
resource "juju_integration" "grafana-agent-k8s-to-cos-prometheus" {
  model = var.model

  application {
    name     = juju_application.grafana-agent-k8s.name
    endpoint = "send-remote-write"
  }

  application {
    offer_url = data.terraform_remote_state.cos.outputs.prometheus-receive-remote-write-offer-url
  }
}

# juju integrate grafana-agent-k8s:logging-consumer cos.loki-logging
resource "juju_integration" "grafana-agent-k8s-to-cos-loki" {
  model = var.model

  application {
    name     = juju_application.grafana-agent-k8s.name
    endpoint = "logging-consumer"
  }

  application {
    offer_url = data.terraform_remote_state.cos.outputs.loki-logging-offer-url
  }
}

# juju integrate grafana-agent-k8s:grafana_dashboard cos.grafana-dashboards
resource "juju_integration" "grafana-agent-k8s-to-cos-grafana" {
  model = var.model

  application {
    name     = juju_application.grafana-agent-k8s.name
    endpoint = "grafana-dashboards-provider"
  }

  application {
    offer_url = data.terraform_remote_state.cos.outputs.grafana-dashboard-offer-url
  }
}
