{{/*
Expand the name of the chart.
*/}}
{{- define "apollosai.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
Truncated at 63 chars because some K8s name fields are limited.
*/}}
{{- define "apollosai.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "apollosai.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "apollosai.labels" -}}
helm.sh/chart: {{ include "apollosai.chart" . }}
{{ include "apollosai.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "apollosai.selectorLabels" -}}
app.kubernetes.io/name: {{ include "apollosai.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use.
*/}}
{{- define "apollosai.serviceAccountName" -}}
{{- default (include "apollosai.fullname" .) .Values.serviceAccountName }}
{{- end }}

{{/*
Secret name — uses existingSecret if set, otherwise generated name.
*/}}
{{- define "apollosai.secretName" -}}
{{- if .Values.existingSecret }}
{{- .Values.existingSecret }}
{{- else }}
{{- include "apollosai.fullname" . }}
{{- end }}
{{- end }}

{{/*
PostgreSQL host — in-cluster service name or external URL.
*/}}
{{- define "apollosai.postgresql.host" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" (include "apollosai.fullname" .) }}
{{- else }}
{{- .Values.postgresql.externalUrl }}
{{- end }}
{{- end }}

{{/*
Redis host — in-cluster service name or external URL.
*/}}
{{- define "apollosai.redis.host" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis" (include "apollosai.fullname" .) }}
{{- else }}
{{- .Values.redis.externalUrl }}
{{- end }}
{{- end }}
