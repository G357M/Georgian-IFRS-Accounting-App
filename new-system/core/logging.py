import logging
import sys
import structlog

def setup_logging(log_level: str = "INFO"):
    """
    Configures structured logging using structlog.
    """
    log_level = log_level.upper()
    
    # Basic logging configuration
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stdout,
    )

    # Structlog configuration
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Render to JSON for machine-readable logs
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Example of how to get a logger in any other module:
    #
    # import structlog
    # logger = structlog.get_logger(__name__)
    #
    # logger.info("User logged in", user_id="123", action="login_success")

# Call this function at the application startup
# For example, in your FastAPI lifespan manager:
#
# from .logging import setup_logging
#
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     setup_logging()
#     ...
