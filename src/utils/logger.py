
import logging

# Configure logging - only log to file, not console (except for interrupts)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_builder.log')
    ]
)
logger = logging.getLogger(__name__)
