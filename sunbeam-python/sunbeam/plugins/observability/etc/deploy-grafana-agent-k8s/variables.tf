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

variable "model" {
  type        = string
  default     = "openstack"
  description = "Name of the model where the application is deployed"
}

variable "cos-state-backend" {
  description = "Backend type used for cos state"
  type        = string
  default     = "http"
}

variable "cos-state-config" {
  type = map(any)
}

variable "grafana-agent-k8s-channel" {
  type        = string
  default     = "latest/stable"
  description = "Operator channel for grafana-agent-k8s deployment"
}

variable "grafana-agent-k8s-revision" {
  type        = number
  default     = null
  description = "Operator channel revision for grafana-agent-k8s deployment"
}

variable "grafana-agent-k8s-config" {
  type        = map(string)
  default     = {}
  description = "Operator config for grafana-agent-k8s deployment"
}
