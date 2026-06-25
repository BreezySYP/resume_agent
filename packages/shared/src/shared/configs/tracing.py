"""shared/configs/tracing.py — OpenTelemetry 全局初始化"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from shared.configs.settings import GRAFANA_URL

_provider = TracerProvider()
if GRAFANA_URL:
    _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=GRAFANA_URL)))
trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("monorepo_agent")
