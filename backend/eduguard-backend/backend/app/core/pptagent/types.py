import enum

class OperateType(str, enum.Enum):
    GENERATE_TITLE_PRESENTATION = "generate_title_presentation"
    GENERATE_OUTLINE = "generate_outline"
    GENERATE_SLIDE_CONTENT = "generate_slide_content"
    GENERATE_PRESENTATION = "generate_presentation"
    IMPROVE_CONTENT = "improve_content"
    GENERATE_SPEAKER_NOTES = "generate_speaker_notes"
    EXTRACT_OUTLINE = "extract_outline"
    IMAGE_SUGGESTIONS = "image_suggestions"
    DOCUMENT_TO_SLIDES = "document_to_slides"
    CONTENT_ENRICHMENT = "content_enrichment"
    SLIDE_ENHANCEMENT = "slide_enhancement"

    def __str__(self):
        return self.value


class PageScopeType(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    COMMUNITY = "community"

    def __str__(self):
        return self.value


class PageCategoryType(str, enum.Enum):
    STRUCTURE = "structure"     # Theo cấu trúc
    COMPONENT = "component"     # Theo thành phần
    SCENE = "scene"             # Theo ngữ cảnh sử dụng

    def __str__(self):
        return self.value


class PageType(str, enum.Enum):
    COVER = "cover"           # Trang bìa
    CONTENTS = "contents"     # Mục lục
    TRANSITION = "transition" # Chuyển đoạn
    CONTENT = "content"       # Nội dung thường
    SECTION = "section"       # Phần riêng biệt
    END = "end"               # Kết thúc

    def __str__(self):
        return self.value


class PageSectionType(str, enum.Enum):
    # === STRUCTURE: Bố cục tổ chức thông tin ===
    TOTAL_SCORE = "total_score"          # Hiển thị điểm số tổng hợp, ranking
    CYCLE = "cycle"                      # Dạng chu kỳ (ví dụ: vòng đời sản phẩm, quy trình lặp)
    PROCESS = "process"                  # Quy trình liên tục theo bước (step 1 → step n)
    HIERARCHY = "hierarchy"              # Phân cấp, tầng lớp thông tin (vd: công ty, hệ thống)
    COMPARISON = "comparison"            # So sánh giữa hai hay nhiều yếu tố
    PARALLEL = "parallel"                # Các yếu tố song song, không phụ thuộc nhau
    OVERVIEW = "overview"
    ROADMAP = "roadmap"
    GRID_LAYOUT = "grid_layout"

    # === COMPONENT: Các thành phần/thị giác đặc trưng ===
    PDCA = "pdca"                        # Biểu đồ PDCA (Plan - Do - Check - Act)
    MAP = "map"                          # Bản đồ (khu vực, thị trường, vị trí)
    FUNNEL = "funnel"                    # Phễu (marketing funnel, conversion funnel)
    GANTT_CHART = "gantt_chart"          # Biểu đồ Gantt (quản lý tiến độ)
    MATRIX = "matrix"                    # Ma trận (SWOT, 2x2, BCG matrix, ...)
    TIMELINE = "timeline"                # Dòng thời gian
    PYRAMID = "pyramid"                  # Hình kim tự tháp (nhấn mạnh ưu tiên từ thấp đến cao)
    ORG_STRUCTURE = "org_structure"      # Sơ đồ tổ chức
    SWOT = "swot"                        # Phân tích SWOT (Strengths, Weaknesses, Opportunities, Threats)
    FISHBONE = "fishbone"                # Biểu đồ xương cá (nguyên nhân - hệ quả)
    CALENDAR = "calendar"                # Lịch (kế hoạch theo tuần, tháng)
    STEPS = "steps"                      # Các bước (có thể khác process ở kiểu trình bày đơn giản hơn)
    # RADAR_CHART = "radar_chart"
    # PIE_CHART = "pie_chart"

    # === SCENE: Bối cảnh ứng dụng thực tế ===
    PRODUCT_INTRO = "product_intro"              # Giới thiệu sản phẩm
    PROJECT_PROGRESS = "project_progress"        # Cập nhật tiến độ dự án
    CONTACT_INFO = "contact_info"                # Thông tin liên hệ
    PERSONAL_INTRO = "personal_intro"            # Giới thiệu cá nhân (hồ sơ, CV)
    WORK_REPORT = "work_report"                  # Báo cáo công việc
    ENTERPRISE_INTRO = "enterprise_intro"        # Giới thiệu doanh nghiệp
    MILESTONE = "milestone"                      # Các cột mốc chính (milestones)
    FAMOUS_QUOTES = "famous_quotes"              # Trích dẫn nổi tiếng
    TEAM_INTRO = "team_intro"                    # Giới thiệu nhóm, tổ chức
    DATA_REPORT = "data_report"                  # Báo cáo dữ liệu (text + số liệu + biểu đồ)
    GRAPHIC_TEXT = "graphic_text"                # Layout phối hợp hình ảnh và văn bản
    EDUCATION_MODULE = "education_module"
    PROPOSAL = "proposal"

    def __str__(self):
        return self.value


TRANSLATION_LABELS = {
    "TOTAL_SCORE": {
        "vi": "Điểm tổng hợp",
        "en": "Total Score",
        "ja": "総合スコア"
    },
    "CYCLE": {
        "vi": "Chu kỳ",
        "en": "Cycle",
        "ja": "サイクル"
    },
    "PROCESS": {
        "vi": "Quy trình",
        "en": "Process",
        "ja": "プロセス"
    },
    "HIERARCHY": {
        "vi": "Phân cấp",
        "en": "Hierarchy",
        "ja": "階層"
    },
    "COMPARISON": {
        "vi": "So sánh",
        "en": "Comparison",
        "ja": "比較"
    },
    "PARALLEL": {
        "vi": "Song song",
        "en": "Parallel",
        "ja": "並列"
    },
    "OVERVIEW": {
        "vi": "Tổng quan",
        "en": "Overview",
        "ja": "概要"
    },
    "ROADMAP": {
        "vi": "Lộ trình",
        "en": "Roadmap",
        "ja": "ロードマップ"
    },
    "GRID_LAYOUT": {
        "vi": "Lưới bố cục",
        "en": "Grid Layout",
        "ja": "グリッドレイアウト"
    },

    # COMPONENT labels
    "PDCA": {
        "vi": "PDCA",
        "en": "PDCA",
        "ja": "PDCA"
    },
    "MAP": {
        "vi": "Bản đồ",
        "en": "Map",
        "ja": "マップ"
    },
    "FUNNEL": {
        "vi": "Phễu",
        "en": "Funnel",
        "ja": "ファネル"
    },
    "GANTT_CHART": {
        "vi": "Gantt",
        "en": "Gantt Chart",
        "ja": "ガントチャート"
    },
    "MATRIX": {
        "vi": "Ma trận",
        "en": "Matrix",
        "ja": "マトリックス"
    },
    "TIMELINE": {
        "vi": "Dòng thời gian",
        "en": "Timeline",
        "ja": "タイムライン"
    },
    "PYRAMID": {
        "vi": "Kim tự tháp",
        "en": "Pyramid",
        "ja": "ピラミッド"
    },
    "ORG_STRUCTURE": {
        "vi": "Sơ đồ tổ chức",
        "en": "Organization Chart",
        "ja": "組織図"
    },
    "SWOT": {
        "vi": "SWOT",
        "en": "SWOT",
        "ja": "SWOT"
    },
    "FISHBONE": {
        "vi": "Xương cá",
        "en": "Fishbone",
        "ja": "フィッシュボーン"
    },
    "CALENDAR": {
        "vi": "Lịch",
        "en": "Calendar",
        "ja": "カレンダー"
    },
    "STEPS": {
        "vi": "Các bước",
        "en": "Steps",
        "ja": "ステップ"
    },

    # SCENE labels
    "PRODUCT_INTRO": {
        "vi": "Giới thiệu sản phẩm",
        "en": "Product Introduction",
        "ja": "製品紹介"
    },
    "PROJECT_PROGRESS": {
        "vi": "Tiến độ dự án",
        "en": "Project Progress",
        "ja": "プロジェクト進捗"
    },
    "CONTACT_INFO": {
        "vi": "Thông tin liên hệ",
        "en": "Contact Information",
        "ja": "連絡先情報"
    },
    "PERSONAL_INTRO": {
        "vi": "Giới thiệu cá nhân",
        "en": "Personal Introduction",
        "ja": "自己紹介"
    },
    "WORK_REPORT": {
        "vi": "Báo cáo công việc",
        "en": "Work Report",
        "ja": "作業報告"
    },
    "ENTERPRISE_INTRO": {
        "vi": "Giới thiệu doanh nghiệp",
        "en": "Enterprise Introduction",
        "ja": "企業紹介"
    },
    "MILESTONE": {
        "vi": "Cột mốc",
        "en": "Milestone",
        "ja": "マイルストーン"
    },
    "FAMOUS_QUOTES": {
        "vi": "Trích dẫn",
        "en": "Famous Quotes",
        "ja": "名言"
    },
    "TEAM_INTRO": {
        "vi": "Giới thiệu nhóm",
        "en": "Team Introduction",
        "ja": "チーム紹介"
    },
    "DATA_REPORT": {
        "vi": "Báo cáo dữ liệu",
        "en": "Data Report",
        "ja": "データレポート"
    },
    "GRAPHIC_TEXT": {
        "vi": "Đồ họa văn bản",
        "en": "Graphic Text",
        "ja": "グラフィックテキスト"
    },
    "EDUCATION_MODULE": {
        "vi": "Giáo dục",
        "en": "Education",
        "ja": "教育"
    },
    "PROPOSAL": {
        "vi": "Đề xuất",
        "en": "Proposal",
        "ja": "提案"
    },

    # SCOPE TYPES
    "SYSTEM": {
        "vi": "Hệ thống",
        "en": "System",
        "ja": "システム"
    },
    "USER": {
        "vi": "Người dùng",
        "en": "User",
        "ja": "ユーザー"
    },
    "COMMUNITY": {
        "vi": "Cộng đồng",
        "en": "Community",
        "ja": "コミュニティ"
    },

    # PAGE TYPES
    "COVER": {
        "vi": "Trang bìa",
        "en": "Cover",
        "ja": "表紙"
    },
    "CONTENTS": {
        "vi": "Mục lục",
        "en": "Contents",
        "ja": "目次"
    },
    "TRANSITION": {
        "vi": "Chuyển đoạn",
        "en": "Transition",
        "ja": "遷移"
    },
    "CONTENT": {
        "vi": "Nội dung",
        "en": "Content",
        "ja": "内容"
    },
    "SECTION": {
        "vi": "Phần",
        "en": "Section",
        "ja": "セクション"
    },
    "END": {
        "vi": "Kết thúc",
        "en": "End",
        "ja": "終了"
    }
}


class ElementType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    SHAPE = "shape"
    CHART = "chart"
    TABLE = "table"
    VIDEO = "video"
    AUDIO = "audio"

    def __str__(self):
        return self.value


class TemplateType(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    COMMUNITY = "community"

    def __str__(self):
        return self.value


class TemplateStatusType(str, enum.Enum):
    DRAFT = "draft"
    PRIVATE = "private"
    PUBLIC = "public"
    FEATURED = "featured"
    ARCHIVED = "archived"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    def __str__(self):
        return self.value


class TemplateCategoryType(str, enum.Enum):
    BUSINESS = "business"
    EDUCATION = "education"
    CREATIVE = "creative"
    MARKETING = "marketing"
    PERSONAL = "personal"
    TECHNOLOGY = "technology"
    MEDICAL = "medical"
    GENERAL = "general"
    OTHER = "other"

    def __str__(self):
        return self.value


class PresentationStatusType(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    DELETED = "deleted"

    def __str__(self):
        return self.value


class DocumentStatusType(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

    def __str__(self):
        return self.value

class PriorityLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    def __str__(self):
        return self.value


class ActivationStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

    def __str__(self):
        return self.value


class CollaboratorRoleType(str, enum.Enum):
    OWNER = "owner"
    EDITOR = "editor"
    COMMENTER = "commenter"
    VIEWER = "viewer"

    def __str__(self):
        return self.value


class CommentStatusType(str, enum.Enum):
    ACTIVE = "active"
    EDITED = "edited"
    DELETED = "deleted"
    HIDDEN = "hidden"

    def __str__(self):
        return self.value
