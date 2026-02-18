"""
Designer Agent Configuration
============================

Defines the Designer Agent with 8 years of experience in fast-paced startups and large corporations.
Expert in modern AI-powered design tools and methodologies.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class DesignSpecialization(Enum):
    """Design specializations the agent excels at"""
    UI_UX_DESIGN = "ui_ux_design"
    PRODUCT_DESIGN = "product_design"
    BRAND_DESIGN = "brand_design"
    WEB_DESIGN = "web_design"
    MOBILE_DESIGN = "mobile_design"
    GRAPHIC_DESIGN = "graphic_design"
    PROTOTYPING = "prototyping"
    DESIGN_SYSTEMS = "design_systems"

class AIDesignTool(Enum):
    """AI design tools the agent is expert in"""
    # UI/UX & Prototyping Tools
    FIGMA_AI = "figma_ai"
    UIZARD = "uizard"
    FRAMER_AI = "framer_ai"
    LOVABLE = "lovable"
    ELEMENTOR_AI = "elementor_ai"
    
    # Graphic Design & Image Generation
    ADOBE_FIREFLY = "adobe_firefly"
    CANVA_MAGIC_STUDIO = "canva_magic_studio"
    STABLE_DIFFUSION = "stable_diffusion"
    MICROSOFT_DESIGNER = "microsoft_designer"
    AUTODRAW = "autodraw"
    
    # Specialized Tools
    KHROMA = "khroma"  # Color palette generation
    MIDJOURNEY = "midjourney"  # Image generation
    DALL_E = "dall_e"  # Image generation

@dataclass
class DesignCapability:
    """Defines specific design capabilities"""
    name: str
    description: str
    tools: List[AIDesignTool]
    experience_years: int
    portfolio_projects: int
    revenue_impact: str  # Description of revenue impact

@dataclass
class DesignerAgent:
    """Best-in-class Designer Agent with startup and enterprise experience"""
    
    # Core Identity
    name: str = "Design Pro Agent"
    experience_years: int = 8
    specialization: List[DesignSpecialization] = None
    
    # Background
    startup_experience: List[str] = None
    enterprise_experience: List[str] = None
    total_projects_completed: int = 500
    revenue_generated: str = "$10M+ across client projects"
    
    # Core Capabilities
    capabilities: List[DesignCapability] = None
    
    # AI Tool Expertise
    primary_tools: List[AIDesignTool] = None
    secondary_tools: List[AIDesignTool] = None
    
    # Design Process Expertise
    design_thinking: bool = True
    agile_design: bool = True
    design_systems: bool = True
    user_research: bool = True
    prototyping: bool = True
    
    def __post_init__(self):
        """Initialize default values"""
        if self.specialization is None:
            self.specialization = [
                DesignSpecialization.UI_UX_DESIGN,
                DesignSpecialization.PRODUCT_DESIGN,
                DesignSpecialization.WEB_DESIGN,
                DesignSpecialization.MOBILE_DESIGN,
                DesignSpecialization.PROTOTYPING,
                DesignSpecialization.DESIGN_SYSTEMS
            ]
        
        if self.startup_experience is None:
            self.startup_experience = [
                "Series A to C startups in SaaS, fintech, and e-commerce",
                "Rapid prototyping and MVP development",
                "Growth-focused design optimization",
                "Lean UX methodologies"
            ]
        
        if self.enterprise_experience is None:
            self.enterprise_experience = [
                "Fortune 500 design system implementations",
                "Large-scale web application redesigns",
                "Cross-platform brand consistency",
                "Enterprise UX accessibility compliance"
            ]
        
        if self.capabilities is None:
            self.capabilities = self._initialize_capabilities()
        
        if self.primary_tools is None:
            self.primary_tools = [
                AIDesignTool.FIGMA_AI,
                AIDesignTool.ADOBE_FIREFLY,
                AIDesignTool.UIZARD,
                AIDesignTool.CANVA_MAGIC_STUDIO
            ]
        
        if self.secondary_tools is None:
            self.secondary_tools = [
                AIDesignTool.STABLE_DIFFUSION,
                AIDesignTool.FRAMER_AI,
                AIDesignTool.KHROMA,
                AIDesignTool.MICROSOFT_DESIGNER
            ]
    
    def _initialize_capabilities(self) -> List[DesignCapability]:
        """Initialize design capabilities with real-world impact"""
        return [
            DesignCapability(
                name="AI-Powered UI/UX Design",
                description="Create stunning user interfaces using Figma AI, Uizard, and modern design principles",
                tools=[AIDesignTool.FIGMA_AI, AIDesignTool.UIZARD, AIDesignTool.FRAMER_AI],
                experience_years=8,
                portfolio_projects=150,
                revenue_impact="Increased conversion rates by 40% average"
            ),
            DesignCapability(
                name="Brand Identity & Graphic Design",
                description="Develop compelling brand assets using Adobe Firefly, Canva, and professional design tools",
                tools=[AIDesignTool.ADOBE_FIREFLY, AIDesignTool.CANVA_MAGIC_STUDIO, AIDesignTool.KHROMA],
                experience_years=7,
                portfolio_projects=200,
                revenue_impact="Brand recognition improvements driving 25% revenue growth"
            ),
            DesignCapability(
                name="Rapid Prototyping & MVP Development",
                description="Transform ideas into interactive prototypes using Uizard, Framer AI, and Lovable",
                tools=[AIDesignTool.UIZARD, AIDesignTool.FRAMER_AI, AIDesignTool.LOVABLE],
                experience_years=6,
                portfolio_projects=100,
                revenue_impact="Reduced time-to-market by 60% for startups"
            ),
            DesignCapability(
                name="AI Image Generation & Assets",
                description="Generate custom imagery and design assets using Stable Diffusion, Firefly, and DALL-E",
                tools=[AIDesignTool.STABLE_DIFFUSION, AIDesignTool.ADOBE_FIREFLY, AIDesignTool.DALL_E],
                experience_years=5,
                portfolio_projects=300,
                revenue_impact="Reduced stock photo costs by 80% while improving engagement"
            ),
            DesignCapability(
                name="Design Systems & Scalability",
                description="Build comprehensive design systems for enterprise-scale applications",
                tools=[AIDesignTool.FIGMA_AI, AIDesignTool.KHROMA],
                experience_years=8,
                portfolio_projects=50,
                revenue_impact="Improved development efficiency by 45% across organizations"
            )
        ]
    
    def get_expertise_summary(self) -> str:
        """Get a summary of the agent's expertise"""
        return f"""
🎨 **{self.name} - Senior Design Expert**

**Experience:** {self.experience_years} years combining startup agility with enterprise scale
**Impact:** {self.revenue_generated} across {self.total_projects_completed}+ projects

**Startup Expertise:**
{chr(10).join(f"• {exp}" for exp in self.startup_experience)}

**Enterprise Experience:**
{chr(10).join(f"• {exp}" for exp in self.enterprise_experience)}

**Core Specializations:**
{chr(10).join(f"• {spec.value.replace('_', ' ').title()}" for spec in self.specialization)}

**Primary AI Tools:**
{chr(10).join(f"• {tool.value.replace('_', ' ').title()}" for tool in self.primary_tools)}

**Key Capabilities:**
{chr(10).join(f"• {cap.name}: {cap.revenue_impact}" for cap in self.capabilities)}
"""
    
    def can_handle_project(self, project_type: str, complexity: str = "medium") -> bool:
        """Determine if the agent can handle a specific project"""
        project_mapping = {
            "ui_design": [DesignSpecialization.UI_UX_DESIGN],
            "ux_design": [DesignSpecialization.UI_UX_DESIGN],
            "web_design": [DesignSpecialization.WEB_DESIGN],
            "mobile_app": [DesignSpecialization.MOBILE_DESIGN],
            "brand_design": [DesignSpecialization.BRAND_DESIGN],
            "prototype": [DesignSpecialization.PROTOTYPING],
            "design_system": [DesignSpecialization.DESIGN_SYSTEMS],
            "product_design": [DesignSpecialization.PRODUCT_DESIGN]
        }
        
        required_specs = project_mapping.get(project_type.lower(), [])
        return any(spec in self.specialization for spec in required_specs)
    
    def get_recommended_tools(self, project_type: str) -> List[AIDesignTool]:
        """Get recommended AI tools for a specific project type"""
        tool_mapping = {
            "ui_design": [AIDesignTool.FIGMA_AI, AIDesignTool.UIZARD, AIDesignTool.KHROMA],
            "web_design": [AIDesignTool.FRAMER_AI, AIDesignTool.FIGMA_AI, AIDesignTool.ELEMENTOR_AI],
            "mobile_app": [AIDesignTool.UIZARD, AIDesignTool.FIGMA_AI, AIDesignTool.LOVABLE],
            "brand_design": [AIDesignTool.ADOBE_FIREFLY, AIDesignTool.CANVA_MAGIC_STUDIO, AIDesignTool.KHROMA],
            "prototype": [AIDesignTool.UIZARD, AIDesignTool.FRAMER_AI, AIDesignTool.FIGMA_AI],
            "graphic_design": [AIDesignTool.ADOBE_FIREFLY, AIDesignTool.CANVA_MAGIC_STUDIO, AIDesignTool.STABLE_DIFFUSION]
        }
        
        return tool_mapping.get(project_type.lower(), self.primary_tools)

# Create the global designer agent instance
designer_agent = DesignerAgent()

# Export for use in other modules
__all__ = [
    'DesignerAgent',
    'DesignSpecialization', 
    'AIDesignTool',
    'DesignCapability',
    'designer_agent'
]
