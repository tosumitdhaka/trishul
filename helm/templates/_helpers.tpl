{{/*
Expand the name of the chart.
*/}}
{{- define "trishul.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "trishul.fullname" -}}
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
{{- define "trishul.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "trishul.labels" -}}
helm.sh/chart: {{ include "trishul.chart" . }}
{{ include "trishul.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "trishul.selectorLabels" -}}
app.kubernetes.io/name: {{ include "trishul.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend labels
*/}}
{{- define "trishul.backend.labels" -}}
{{ include "trishul.labels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Frontend labels
*/}}
{{- define "trishul.frontend.labels" -}}
{{ include "trishul.labels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
MySQL labels
*/}}
{{- define "trishul.mysql.labels" -}}
{{ include "trishul.labels" . }}
app.kubernetes.io/component: mysql
{{- end }}

{{/*
Return the proper image name for backend
*/}}
{{- define "trishul.backend.image" -}}
{{- $registry := .Values.image.backend.registry | default .Values.global.imageRegistry -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry .Values.image.backend.repository .Values.image.backend.tag -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.backend.repository .Values.image.backend.tag -}}
{{- end -}}
{{- end -}}

{{/*
Return the proper image name for frontend
*/}}
{{- define "trishul.frontend.image" -}}
{{- $registry := .Values.image.frontend.registry | default .Values.global.imageRegistry -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry .Values.image.frontend.repository .Values.image.frontend.tag -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.frontend.repository .Values.image.frontend.tag -}}
{{- end -}}
{{- end -}}

{{/*
Return the proper image name for MySQL
*/}}
{{- define "trishul.mysql.image" -}}
{{- $registry := .Values.image.mysql.registry | default .Values.global.imageRegistry -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry .Values.image.mysql.repository .Values.image.mysql.tag -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.mysql.repository .Values.image.mysql.tag -}}
{{- end -}}
{{- end -}}
