# backend/services/form_processor.py
"""
Form processor service that orchestrates the entire flow:
Image → LLM → Agent Processing → Storage

"""

import re
import json
import aiohttp
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, UTC

from config.settings import settings
from agents.itf_agent import ITFAgent
from agents.nar_agent import NARAgent
from services.storage_service import StorageService

logger = logging.getLogger(__name__)

# Form type agent mapping
FORM_TYPE_AGENTS = {
    "ITF": ITFAgent,
    "NAR": NARAgent,
}


class FormProcessor:
    """
    Main form processor that orchestrates the entire pipeline.

    Pipeline:
    1. Image validation
    2. Prompt loading/validation
    3. LLM processing (Qwen)
    4. Agent-based data extraction
    5. Storage (MongoDB + MinIO)
    """

    def __init__(
        self,
        storage_service: StorageService,
        mongo_client=None,
    ):
        """
        Initialize form processor.

        Args:
            storage_service: StorageService instance for persistence
            mongo_client: Optional MongoClient instance (for health checks)

        Raises:
            ValueError: If storage_service is None
        """
        if storage_service is None:
            raise ValueError("storage_service cannot be None")

        # ✅ Store as both self.storage AND self.storage_service
        # Health check expects self.storage_service
        self.storage = storage_service
        self.storage_service = storage_service

        # ✅ Store mongo_client for health checks
        self.mongo_client = mongo_client

        # ✅ Get SSL context for secure connections
        self.ssl_context = settings.get_ssl_context()

        logger.info("📋 data BRIDGE LLM form processor initialized")
        logger.debug(f"   Storage service: {type(self.storage).__name__}")
        logger.debug(f"   Mongo client: {'initialized' if mongo_client else 'not provided'}")
        logger.debug(f"   SSL context: {'configured' if self.ssl_context else 'not configured'}")

    @staticmethod
    def extract_page_number(image_path: Path) -> Optional[int]:
        """
        Extract page number from image filename.

        Supports patterns like:
        - ITF_40000071_page_1.png -> 1
        - ITF_40000071_p1.png -> 1
        - ITF_40000071_1.png -> 1

        Args:
            image_path: Path to image file

        Returns:
            int: Page number if found, None otherwise
        """
        filename = image_path.stem.lower()

        # Try "page_N" pattern
        match = re.search(r'page[_-]?(\d+)', filename)
        if match:
            return int(match.group(1))

        # Try "_pN" pattern
        match = re.search(r'_p(\d+)$', filename)
        if match:
            return int(match.group(1))

        # Try trailing number pattern
        match = re.search(r'_(\d+)$', filename)
        if match:
            return int(match.group(1))

        return None

    @staticmethod
    def extract_form_type_from_filename(file_name: str) -> Optional[str]:
        """
        Extract form type from filename.

        Supports patterns like:
        - ITF_40000071_page_1.png -> ITF
        - NAR_40000071_p1.png -> NAR
        - DSC_40000071_1.png -> DSC
        - ITF-40000071-page-1.png -> ITF
        - itf_form_001.png -> ITF

        Args:
            file_name: Filename string (e.g., from file.filename)

        Returns:
            str: Form type if found (uppercase), None otherwise
        """
        if not file_name or not isinstance(file_name, str):
            return None

        # Get the stem (filename without extension)
        stem = Path(file_name).stem.upper()

        logger.debug(f"🔍 Extracting form type from: {file_name} (stem: {stem})")

        # Known form type prefixes
        FORM_TYPES = settings.FORM_TYPES

        # Try exact prefix match (e.g., "ITF_40000071_page_1")
        for form_type in FORM_TYPES:
            if stem.startswith(form_type):
                # Ensure it's a word boundary (e.g., ITF- or ITF_)
                if len(stem) > len(form_type):
                    next_char = stem[len(form_type)]
                    if next_char in ["_", "-"]:
                        logger.debug(f"✅ Detected form type: {form_type}")
                        return form_type

        # Try pattern matching with regex (e.g., "FORM_ITF_001")
        pattern = r"(?:^|_|-)(" + "|".join(FORM_TYPES) + r")(?:_|-|$)"
        match = re.search(pattern, stem)
        if match:
            form_type = match.group(1)
            logger.debug(f"✅ Detected form type (regex): {form_type}")
            return form_type

        # Try containment check as last resort (e.g., "MY_ITF_FORM")
        for form_type in FORM_TYPES:
            if form_type in stem.split("_") or form_type in stem.split("-"):
                logger.debug(f"✅ Detected form type (containment): {form_type}")
                return form_type

        logger.warning(f"⚠️  Could not detect form type from: {file_name}")
        return None

    @staticmethod
    def load_prompt_from_file(
        form_type: str,
        page_number: Optional[int] = None,
        use_fallback: bool = True,
    ) -> str:
        """
        Load prompt from file based on form type and page number.

        Args:
            form_type: Form type identifier (e.g., 'ITF', 'NAR')
            page_number: Page number (optional)
            use_fallback: Use DEFAULT.txt if specific prompt not found

        Returns:
            str: Prompt text loaded from file

        Raises:
            FileNotFoundError: If prompt file not found and fallback disabled
            ValueError: If form_type is invalid
        """
        form_type_upper = form_type.upper().strip()

        if not form_type_upper:
            raise ValueError("form_type cannot be empty")

        # Build filename
        if page_number is not None:
            prompt_filename = f"{form_type_upper}_{page_number}.txt"
        else:
            prompt_filename = f"{form_type_upper}.txt"

        prompt_path = Path(settings.PROMPTS_DIR) / prompt_filename

        logger.debug(f"🔍 Looking for prompt: {prompt_path}")

        # Try specific prompt first
        if prompt_path.exists():
            try:
                content = prompt_path.read_text(encoding="utf-8").strip()
                logger.info(f"📄 Loaded prompt from: {prompt_filename}")
                return content
            except Exception as e:
                logger.error(f"❌ Error reading prompt file: {e}")
                if not use_fallback:
                    raise

        # Try fallback prompt
        if use_fallback and settings.DEFAULT_PROMPT_FALLBACK:
            fallback_path = Path(settings.PROMPTS_DIR) / settings.DEFAULT_PROMPT_FILE

            if fallback_path.exists():
                try:
                    content = fallback_path.read_text(encoding="utf-8").strip()
                    logger.warning(f"⚠️  Using fallback prompt")
                    return content
                except Exception as e:
                    logger.error(f"❌ Error reading fallback: {e}")
                    raise

        raise FileNotFoundError(
            f"Prompt not found: {prompt_filename} or {settings.DEFAULT_PROMPT_FILE}"
        )

    @staticmethod
    def strip_markdown_code_blocks(text: str) -> str:
        """Strip markdown code blocks from text."""
        if not isinstance(text, str):
            return text

        pattern = r"```(?:json|python|javascript|yaml)?\n(.*?)\n```"
        match = re.search(pattern, text, re.DOTALL)

        if match:
            content = match.group(1)
            logger.debug(f"🔍 Stripped markdown code block")
            return content

        return text

    @staticmethod
    def get_agent_for_form_type(form_type: str):
        """
        Get the appropriate agent for the given form type.

        Args:
            form_type: Form type identifier (e.g., 'ITF', 'NAR')

        Returns:
            Agent class (not instantiated)

        Raises:
            ValueError: If form type is not supported
        """
        form_type_upper = form_type.upper().strip()

        if form_type_upper not in FORM_TYPE_AGENTS:
            supported = ", ".join(FORM_TYPE_AGENTS.keys())
            raise ValueError(
                f"Unsupported form type: '{form_type}'. "
                f"Supported: {supported}"
            )

        return FORM_TYPE_AGENTS[form_type_upper]

    async def _process_with_agent(
        self,
        response_text: str,
        image_path: Path,
        form_type: str = "ITF",
        page_number: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        """
        Process LLM response through form agent.

        Args:
            response_text: Raw LLM response text
            image_path: Path to original image
            form_type: Form type identifier
            page_number: Page number (optional)

        Returns:
            Tuple of (raw_json, cleaned_json, case_summary)
        """
        try:
            form_type_upper = form_type.upper()
            logger.debug(f"🤖 Processing with {form_type_upper} agent...")

            # Parse raw response
            try:
                raw_json = json.loads(response_text)
                logger.debug(f"✅ Parsed response as JSON")
            except json.JSONDecodeError:
                logger.warning(f"⚠️  Response is not valid JSON")
                raw_json = {"response": response_text}

            # Get agent
            try:
                agent_class = self.get_agent_for_form_type(form_type)
            except ValueError as e:
                logger.warning(f"⚠️  {str(e)}")
                return (raw_json, {}, f"Agent error: {str(e)}")

            # Create temp markdown file
            temp_md = Path(
                f"{settings.UPLOAD_TEMP_DIR}/{form_type_upper.lower()}_{image_path.stem}.md"
            )

            if isinstance(raw_json, dict):
                md_content = f"\n```json\n"
                md_content += json.dumps(raw_json, indent=2)
                md_content += "\n```\n"
            else:
                md_content = f"\n{response_text}\n"

            temp_md.write_text(md_content, encoding="utf-8")
            logger.debug(f"📝 Created temp markdown: {temp_md}")

            # Process with agent
            if page_number is None:
                page_number = self.extract_page_number(image_path) or 1

            agent = agent_class(page_number)

            # Call appropriate method
            if hasattr(agent, "process_itf_file"):
                result = await agent.process_itf_file(str(temp_md))
            elif hasattr(agent, "process_nar_file"):
                result = await agent.process_nar_file(str(temp_md))
            elif hasattr(agent, "process_file"):
                result = await agent.process_file(str(temp_md))
            else:
                raise AttributeError("Agent missing process method")

            # Cleanup
            try:
                temp_md.unlink()
            except Exception as e:
                logger.warning(f"⚠️  Could not cleanup temp file: {e}")

            # Extract results
            if result.get("status") == "success":
                cleaned_json = (
                    result.get("sections")
                    or result.get("data")
                    or result.get("cleaned_data")
                    or {}
                )
                case_summary = result.get("summary") or result.get("report") or ""
                coverage = result.get("coverage")
                completeness = result.get("completeness")

                logger.info(f"✅ Agent processing complete")
                return raw_json, cleaned_json, case_summary, coverage, completeness
            else:
                error_msg = result.get("error", "Unknown error")
                logger.warning(f"⚠️  Agent error: {error_msg}")
                return raw_json, {}, f"Agent error: {error_msg}"

        except Exception as e:
            logger.error(f"❌ Agent processing failed: {e}", exc_info=True)
            try:
                raw_json = json.loads(response_text)
            except:
                raw_json = {"response": response_text}

            return raw_json, {}, f"Error: {str(e)}"

    async def process(
        self,
        image_path: str,
        prompt: Optional[str] = None,
        form_type: str = "ITF",
        page_number: Optional[int] = None,
        case_id: Optional[str] = None,
        save_to_storage: bool = True,
        process_with_agent: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a form image through the complete pipeline.

        This is the main entry point for form processing and is expected
        by the health check and upload routes.

        Pipeline:
        1. Validate image
        2. Load/validate prompt
        3. Send to Qwen LLM
        4. Process with form agent
        5. Save to MongoDB + MinIO

        Args:
            image_path: Path to form image
            prompt: Custom prompt (loads from file if None)
            form_type: Form type (default: ITF)
            page_number: Page number for prompt
            case_id: Optional case ID for organization
            save_to_storage: Save results to MongoDB/MinIO
            process_with_agent: Process response with form agent

        Returns:
            dict: Complete processing result including:
                - response: LLM response text
                - raw_json: Parsed JSON response
                - cleaned_json: Extracted structured data
                - case_summary: Human-readable summary
                - metadata: Processing metadata
                - mongo_id: MongoDB document ID (if saved)

        Raises:
            FileNotFoundError: If image or prompt file not found
            ValueError: If form type unsupported or API error
        """
        image_path = Path(image_path).resolve()
        form_type_upper = form_type.upper()

        # ==================== STEP 1: VALIDATE IMAGE ====================
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        file_size_mb = image_path.stat().st_size / (1024 * 1024)
        logger.info(f"📸 Processing: {image_path.name} ({file_size_mb:.2f} MB)")
        logger.info(f"📋 Form Type: {form_type_upper}")

        # ==================== STEP 2: LOAD/VALIDATE PROMPT ====================
        if prompt is None:
            # Auto-detect page number if not provided
            if page_number is None:
                detected = self.extract_page_number(image_path)
                if detected:
                    page_number = detected
                    logger.debug(f"🔍 Auto-detected page: {page_number}")

            # Load prompt from file
            prompt = self.load_prompt_from_file(
                form_type=form_type,
                page_number=page_number,
                use_fallback=True,
            )

        logger.debug(f"💬 Prompt: {prompt[:100]}...")

        # ==================== STEP 3: SEND TO LLM ====================
        logger.info(f"🔗 Sending to Qwen: {settings.QWEN_SERVICE_URL}")

        start_time = datetime.now(UTC)
        result = await self._call_qwen_api(image_path, prompt)
        llm_elapsed = (datetime.now(UTC) - start_time).total_seconds()

        if "error" in result:
            logger.error(f"❌ LLM error: {result['error']}")
            return result

        response_text = result.get("response", "")
        response_text = self.strip_markdown_code_blocks(response_text)

        # ==================== STEP 4: PROCESS WITH AGENT ====================
        if process_with_agent:
            start_process_time = datetime.now(UTC)
            logger.info(f"🤖 Processing with {form_type_upper} agent...")
            raw_json, cleaned_json, case_summary, coverage, completeness = await self._process_with_agent(
                response_text,
                image_path,
                form_type=form_type,
                page_number=page_number,
            )

            agent_elapsed = (datetime.now(UTC) - start_process_time).total_seconds()

            result["raw_json"] = raw_json
            result["cleaned_json"] = cleaned_json
            result["case_summary"] = case_summary
            result["coverage"] = coverage
            result["completeness"] = completeness
        else:
            try:
                result["raw_json"] = json.loads(response_text)
            except:
                result["raw_json"] = {"response": response_text}

            result["cleaned_json"] = {}
            result["case_summary"] = ""

        result["form_type"] = form_type_upper
        result["agent_processed"] = process_with_agent

        # ==================== STEP 5: SAVE TO STORAGE ====================
        mongo_id = None
        if save_to_storage:
            logger.info(f"💾 Saving to storage...")

            # Save to MongoDB + MinIO
            mongo_id = await self.storage.save_form_processing_result(
                result=result,
                image_filename=image_path.name,
                form_type=form_type_upper,
                metadata={
                    "case_id": image_path.name,
                    "page_number": page_number,
                    "file_size_mb": file_size_mb,
                    "processing_time_llm_seconds": llm_elapsed,
                    "processing_time_agent_seconds": agent_elapsed
                },
            )

            # Also save original document
            doc_key = await self.storage.save_form_document(
                file_path=str(image_path),
                form_type=form_type_upper,
                case_id=case_id,
            )

            if mongo_id:
                result["mongo_id"] = mongo_id
                logger.info(f"✅ Saved with ID: {mongo_id}")
            if doc_key:
                result["document_s3_key"] = doc_key
                logger.info(f"✅ Document saved to S3: {doc_key}")

        return result

    async def process_form(
        self,
        image_path: str,
        prompt: Optional[str] = None,
        form_type: str = "ITF",
        page_number: Optional[int] = None,
        case_id: Optional[str] = None,
        save_to_storage: bool = True,
        process_with_agent: bool = True,
    ) -> Dict[str, Any]:
        """
        Alias for process() method for backward compatibility.

        Delegates to the main process() method.
        """
        return await self.process(
            image_path=image_path,
            prompt=prompt,
            form_type=form_type,
            page_number=page_number,
            case_id=case_id,
            save_to_storage=save_to_storage,
            process_with_agent=process_with_agent,
        )

    async def _call_qwen_api(
        self,
        image_path: Path,
        prompt: str,
        timeout: int = 600,
    ) -> Dict[str, Any]:
        """
        Call Qwen API with image and prompt.

        Args:
            image_path: Path to image file
            prompt: Text prompt
            timeout: Request timeout in seconds

        Returns:
            dict: API response with keys:
                - response: LLM response text
                - error: Error message if failed

        Note:
            Uses SSL context from settings for self-signed certificate handling.
        """
        try:
            with open(image_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("image", f, filename=image_path.name)
                data.add_field("prompt", prompt)

                connector = aiohttp.TCPConnector(ssl=self.ssl_context)
                timeout_obj = aiohttp.ClientTimeout(total=timeout)

                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(
                        f"{settings.QWEN_SERVICE_URL}/generate-with-image",
                        data=data,
                        timeout=timeout_obj,
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"❌ API error {response.status}: {error_text}")
                            return {
                                "error": f"API error {response.status}",
                                "details": error_text,
                            }

                        result = await response.json()
                        logger.info(f"✅ Received LLM response")
                        return result

        except aiohttp.ClientError as e:
            logger.error(f"❌ Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}", exc_info=True)
            return {"error": str(e)}
