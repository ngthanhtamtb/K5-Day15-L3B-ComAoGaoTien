from typing import Dict, List, Any, Optional
from app.core.pptagent.types import TRANSLATION_LABELS, PageType, PageScopeType, PageCategoryType, PageSectionType


class MultiLanguageTemplateFilters:
    def __init__(self, default_language: str = "en"):
        self.default_language = default_language
        self.supported_languages = ["vi", "en", "ja"]

    def get_label(self, key: str, language: str = None) -> str:
        if language is None:
            language = self.default_language

        if key in TRANSLATION_LABELS:
            return TRANSLATION_LABELS[key].get(language, TRANSLATION_LABELS[key].get(self.default_language, key))
        return key

    def get_page_type_groups(self, language: str = None) -> Dict[PageCategoryType, List[Dict[str, Any]]]:
        if language is None:
            language = self.default_language

        return {
            PageCategoryType.STRUCTURE: [
                {"value": PageSectionType.TOTAL_SCORE, "label": self.get_label("TOTAL_SCORE", language)},
                {"value": PageSectionType.CYCLE, "label": self.get_label("CYCLE", language)},
                {"value": PageSectionType.PROCESS, "label": self.get_label("PROCESS", language)},
                {"value": PageSectionType.HIERARCHY, "label": self.get_label("HIERARCHY", language)},
                {"value": PageSectionType.COMPARISON, "label": self.get_label("COMPARISON", language)},
                {"value": PageSectionType.PARALLEL, "label": self.get_label("PARALLEL", language)},
                {"value": PageSectionType.OVERVIEW, "label": self.get_label("OVERVIEW", language)},
                {"value": PageSectionType.ROADMAP, "label": self.get_label("ROADMAP", language)},
                {"value": PageSectionType.GRID_LAYOUT, "label": self.get_label("GRID_LAYOUT", language)},
            ],

            PageCategoryType.COMPONENT: [
                {"value": PageSectionType.PDCA, "label": self.get_label("PDCA", language)},
                {"value": PageSectionType.MAP, "label": self.get_label("MAP", language)},
                {"value": PageSectionType.FUNNEL, "label": self.get_label("FUNNEL", language)},
                {"value": PageSectionType.GANTT_CHART, "label": self.get_label("GANTT_CHART", language)},
                {"value": PageSectionType.MATRIX, "label": self.get_label("MATRIX", language)},
                {"value": PageSectionType.TIMELINE, "label": self.get_label("TIMELINE", language)},
                {"value": PageSectionType.PYRAMID, "label": self.get_label("PYRAMID", language)},
                {"value": PageSectionType.ORG_STRUCTURE, "label": self.get_label("ORG_STRUCTURE", language)},
                {"value": PageSectionType.SWOT, "label": self.get_label("SWOT", language)},
                {"value": PageSectionType.FISHBONE, "label": self.get_label("FISHBONE", language)},
                {"value": PageSectionType.CALENDAR, "label": self.get_label("CALENDAR", language)},
                {"value": PageSectionType.STEPS, "label": self.get_label("STEPS", language)},
            ],

            PageCategoryType.SCENE: [
                {"value": PageSectionType.PRODUCT_INTRO, "label": self.get_label("PRODUCT_INTRO", language)},
                {"value": PageSectionType.PROJECT_PROGRESS, "label": self.get_label("PROJECT_PROGRESS", language)},
                {"value": PageSectionType.CONTACT_INFO, "label": self.get_label("CONTACT_INFO", language)},
                {"value": PageSectionType.PERSONAL_INTRO, "label": self.get_label("PERSONAL_INTRO", language)},
                {"value": PageSectionType.WORK_REPORT, "label": self.get_label("WORK_REPORT", language)},
                {"value": PageSectionType.ENTERPRISE_INTRO, "label": self.get_label("ENTERPRISE_INTRO", language)},
                {"value": PageSectionType.MILESTONE, "label": self.get_label("MILESTONE", language)},
                {"value": PageSectionType.FAMOUS_QUOTES, "label": self.get_label("FAMOUS_QUOTES", language)},
                {"value": PageSectionType.TEAM_INTRO, "label": self.get_label("TEAM_INTRO", language)},
                {"value": PageSectionType.DATA_REPORT, "label": self.get_label("DATA_REPORT", language)},
                {"value": PageSectionType.GRAPHIC_TEXT, "label": self.get_label("GRAPHIC_TEXT", language)},
                {"value": PageSectionType.EDUCATION_MODULE, "label": self.get_label("EDUCATION_MODULE", language)},
                {"value": PageSectionType.PROPOSAL, "label": self.get_label("PROPOSAL", language)},
            ]
        }

    def get_scope_types(self, language: str = None) -> List[Dict[str, Any]]:
        if language is None:
            language = self.default_language

        return [
            {"value": PageScopeType.SYSTEM, "label": self.get_label("SYSTEM", language)},
            {"value": PageScopeType.USER, "label": self.get_label("USER", language)},
            {"value": PageScopeType.COMMUNITY, "label": self.get_label("COMMUNITY", language)},
        ]

    def get_page_types(self, language: str = None) -> List[Dict[str, Any]]:
        if language is None:
            language = self.default_language

        return [
            {"value": PageType.COVER, "label": self.get_label("COVER", language)},
            {"value": PageType.CONTENTS, "label": self.get_label("CONTENTS", language)},
            {"value": PageType.TRANSITION, "label": self.get_label("TRANSITION", language)},
            {"value": PageType.CONTENT, "label": self.get_label("CONTENT", language)},
            {"value": PageType.SECTION, "label": self.get_label("SECTION", language)},
            {"value": PageType.END, "label": self.get_label("END", language)},
        ]