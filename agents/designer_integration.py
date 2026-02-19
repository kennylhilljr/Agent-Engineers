"""
Designer Agent Integration
==========================

Integration of the Designer Agent into the main agent system.
"""

from agents.designer_agent import designer_agent, DesignerAgent, DesignSpecialization, AIDesignTool
from bridges.designer_bridge import DesignerBridge


def register_designer_agent():
    """Register the designer agent with the main system"""
    
    # Add designer agent to available agents
    from agents.definitions import agent_definitions
    
    agent_definitions["designer"] = {
        "class": DesignerAgent,
        "bridge": DesignerBridge,
        "description": "Best-in-class designer with 8 years experience in startups and enterprises. Expert in AI-powered design tools including Figma AI, Adobe Firefly, Uizard, and more.",
        "capabilities": [
            "UI/UX design with AI tools",
            "Brand identity creation", 
            "Rapid prototyping and MVP development",
            "AI image generation",
            "Design system creation",
            "Cross-platform design consistency"
        ],
        "tools": [
            "Figma AI",
            "Adobe Firefly", 
            "Uizard",
            "Canva Magic Studio",
            "Stable Diffusion",
            "Framer AI",
            "Lovable",
            "Khroma"
        ],
        "specializations": [
            "Startup MVP design",
            "Enterprise design systems",
            "Mobile app design",
            "Web application design",
            "Brand design",
            "Prototyping"
        ]
    }
    
    return designer_agent


def get_designer_agent():
    """Get the designer agent instance"""
    return designer_agent


def get_designer_bridge():
    """Get a new designer bridge instance"""
    return DesignerBridge()


# Designer agent prompt templates
DESIGNER_PROMPTS = {
    "ui_design": """
You are a senior UI/UX designer with 8 years of experience at successful startups and enterprises.

Using your expertise with Figma AI, Uizard, and modern design tools, create a stunning user interface that:

1. Follows modern design principles and best practices
2. Optimizes for user experience and conversion
3. Incorporates the brand identity and style guide
4. Is responsive and accessible
5. Uses AI-powered design tools efficiently

Generate:
- Complete UI design specifications
- Component library
- Design system tokens
- Interactive prototype
- Design rationale and decisions

Focus on creating designs that drive business results and user satisfaction.
""",

    "brand_design": """
You are an expert brand designer with 8 years of experience creating successful brand identities.

Using Adobe Firefly, Canva Magic Studio, and professional design tools, create a comprehensive brand identity that:

1. Reflects the company's values and mission
2. Stands out in the market
3. Resonates with the target audience
4. Is scalable across all touchpoints
5. Includes complete brand guidelines

Generate:
- Logo concepts and final designs
- Color palette and typography system
- Brand guidelines document
- Marketing asset templates
- Brand application examples

Focus on creating memorable, impactful brands that drive recognition and trust.
""",

    "prototype": """
You are a prototyping expert with extensive experience in rapid MVP development.

Using Uizard, Framer AI, and Lovable, create interactive prototypes that:

1. Demonstrate core functionality clearly
2. Provide realistic user experience
3. Support user testing and validation
4. Are optimized for the target platform
5. Include proper user flows and interactions

Generate:
- Interactive prototype files
- User flow diagrams
- Interaction specifications
- Responsive breakpoints
- Testing scenarios

Focus on creating prototypes that effectively validate concepts and guide development.
"""
}


def get_designer_prompt(task_type: str) -> str:
    """Get the appropriate designer prompt for a task type"""
    return DESIGNER_PROMPTS.get(task_type, DESIGNER_PROMPTS["ui_design"])


# Export for use in other modules
__all__ = [
    'register_designer_agent',
    'get_designer_agent', 
    'get_designer_bridge',
    'get_designer_prompt',
    'DESIGNER_PROMPTS'
]
