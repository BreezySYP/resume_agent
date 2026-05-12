"""
config/tracing.py
OpenTelemetry + Grafana/Tempo 初始化，其他模块直接 import tracer 使用。
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from src.configs.settings import GRAFANA_URL

_provider = TracerProvider()

if GRAFANA_URL:
    _exporter = OTLPSpanExporter(endpoint=GRAFANA_URL)
    _provider.add_span_processor(BatchSpanProcessor(_exporter))

trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("dev_agent")