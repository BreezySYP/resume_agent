"""shared/configs/tracing.py — OpenTelemetry 全局初始化"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from shared.configs.settings import TEMPO_URL

_provider = TracerProvider()
if TEMPO_URL:
    _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=TEMPO_URL)))
trace.set_tracer_provider(_provider)

def get_tracer(module_name):
    return trace.get_tracer(module_name)

def span_error(span: trace.Span, e: Exception):
    span.record_exception(e)  # 自动记录异常堆栈
    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
    # 记录错误信息到属性
    span.set_attribute("error.type", type(e).__name__)
    span.set_attribute("error.message", str(e))
