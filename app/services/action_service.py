# app/services/action_service.py
from app.services.local_actions_service import LocalActionsService
from app.services.development_service import DevelopmentService
from app.services.browser_service import BrowserService
from app.services.browser_navigation_service import BrowserNavigationService
from app.services.web_extraction_service import WebExtractionService
from app.services.webpage_analysis_service import WebpageAnalysisService
from app.services.browser_workflow_service import BrowserWorkflowService
from app.services.browser_memory_service import BrowserMemoryService
from app.services.desktop_service import DesktopService

class ActionService:
    """Central registry mapping declarative string actions directly to their execution service methods."""
    def __init__(self):
        self.local_actions = LocalActionsService()
        self.development_service = DevelopmentService()
        self.browser_service = BrowserService()
        self.memory_service = BrowserMemoryService()
        self.navigation_service = BrowserNavigationService(self.browser_service, self.memory_service)
        self.extraction_service = WebExtractionService()
        self.analysis_service = WebpageAnalysisService()
        self.workflow_service = BrowserWorkflowService(self.navigation_service, self.memory_service)
        self.desktop_service = DesktopService()
        
        self.registry = {
            "create_folder": self.local_actions.create_folder,
            "create_file": self.local_actions.create_file,
            "execute_terminal": self.local_actions.execute_terminal,
            "create_project": self.development_service.provision_new_project,
            "analyze_code": self.development_service.execute_and_analyze_file,
            "test_run": self.development_service.test_run_script,
            "browser_search": self._handle_async_search,
            "browser_navigate": self.navigation_service.navigate_to_url,
            "web_extract": self._handle_async_extraction,
            "web_analyze": self.analysis_service.parse_page_structure,
            # Phase 4 Implementations utilizing Async Wrappers to bypass Synchronous Execution router limits
            "desktop_launch": self._handle_desktop_launch,
            "system_status": self._handle_system_status,
            "environment_check": self._handle_environment_check,
            "desktop_mouse": self._handle_desktop_mouse,
            "desktop_keyboard": self._handle_desktop_keyboard
        }

    async def _handle_desktop_launch(self, target: str, content: str = None):
        return self.desktop_service.launch_application(target, content)

    async def _handle_system_status(self, target: str, content: str = None):
        return self.desktop_service.get_system_status(target, content)

    async def _handle_environment_check(self, target: str, content: str = None):
        return self.desktop_service.check_environment(target, content)

    async def _handle_desktop_mouse(self, target: str, content: str = None):
        return self.desktop_service.mouse_action(target, content)

    async def _handle_desktop_keyboard(self, target: str, content: str = None):
        return self.desktop_service.keyboard_action(target, content)

    async def _handle_async_search(self, query: str, custom_path: str = None) -> str:
        """Executes search workflow AND automatically saves the results to a custom or default path."""
        try:
            wf_res = await self.workflow_service.execute_browser_workflow("google_search", {"query": query})
            if not wf_res.get("success"):
                return f"Search workflow failed: {wf_res.get('error')}"
                
            page = await self.navigation_service.get_active_page()
            
            safe_query_name = "".join(c if c.isalnum() else "_" for c in query[:15])
            filename_slug = f"search_results_{safe_query_name}"
            
            extract_res = await self.extraction_service.extract_and_save_page(page, filename_slug, custom_path)
            
            if extract_res.get("success"):
                snippet = extract_res.get("content_snippet", "")
                return (
                    f"Successfully searched for '{query}'.\n"
                    f"Results page scraped and saved to: {extract_res.get('saved_path')}\n\n"
                    f"--- EXTRACTED PAGE CONTENT FOR SUMMARY ---\n"
                    f"{snippet}\n"
                    f"------------------------------------------"
                )
            return f"Search succeeded, but automatic result scraping failed: {extract_res.get('error')}"
        finally:
            await self.browser_service.close_browser()

    async def _handle_async_extraction(self, filename_slug: str) -> str:
        page = await self.navigation_service.get_active_page()
        res = await self.extraction_service.extract_and_save_page(page, filename_slug)
        if res.get("success"):
            return f"Successfully extracted markdown page layer. File saved to: {res.get('saved_path')}"
        return f"Scraping extraction error occurred: {res.get('error')}"

    def get_handler(self, action_name: str):
        return self.registry.get(action_name)
        
    def is_valid_action(self, action_name: str) -> bool:
        return action_name in self.registry