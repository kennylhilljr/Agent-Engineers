"""
Designer Agent Tests
====================

Tests for the Designer Agent functionality.
"""

import pytest
import asyncio
from pathlib import Path

from agents.designer_agent import designer_agent, DesignerAgent, DesignSpecialization, AIDesignTool
from bridges.designer_bridge import DesignerBridge


class TestDesignerAgent:
    """Test the Designer Agent configuration and capabilities"""
    
    def test_agent_initialization(self):
        """Test that the designer agent initializes correctly"""
        assert designer_agent.name == "Design Pro Agent"
        assert designer_agent.experience_years == 8
        assert len(designer_agent.specialization) >= 5
        assert len(designer_agent.capabilities) >= 4
    
    def test_specializations(self):
        """Test design specializations"""
        expected_specs = [
            DesignSpecialization.UI_UX_DESIGN,
            DesignSpecialization.PRODUCT_DESIGN,
            DesignSpecialization.WEB_DESIGN,
            DesignSpecialization.MOBILE_DESIGN,
            DesignSpecialization.PROTOTYPING
        ]
        
        for spec in expected_specs:
            assert spec in designer_agent.specialization
    
    def test_ai_tools(self):
        """Test AI tool expertise"""
        expected_tools = [
            AIDesignTool.FIGMA_AI,
            AIDesignTool.ADOBE_FIREFLY,
            AIDesignTool.UIZARD,
            AIDesignTool.CANVA_MAGIC_STUDIO
        ]
        
        for tool in expected_tools:
            assert tool in designer_agent.primary_tools
    
    def test_project_handling(self):
        """Test project type handling"""
        assert designer_agent.can_handle_project("ui_design")
        assert designer_agent.can_handle_project("web_design")
        assert designer_agent.can_handle_project("mobile_app")
        assert designer_agent.can_handle_project("brand_design")
        assert designer_agent.can_handle_project("prototype")
    
    def test_tool_recommendations(self):
        """Test tool recommendations for project types"""
        ui_tools = designer_agent.get_recommended_tools("ui_design")
        assert AIDesignTool.FIGMA_AI in ui_tools
        assert AIDesignTool.UIZARD in ui_tools
        
        brand_tools = designer_agent.get_recommended_tools("brand_design")
        assert AIDesignTool.ADOBE_FIREFLY in brand_tools
        assert AIDesignTool.CANVA_MAGIC_STUDIO in brand_tools
    
    def test_expertise_summary(self):
        """Test expertise summary generation"""
        summary = designer_agent.get_expertise_summary()
        assert "Design Pro Agent" in summary
        assert "8 years" in summary
        assert "startup" in summary.lower()
        assert "enterprise" in summary.lower()


class TestDesignerBridge:
    """Test the Designer Bridge functionality"""
    
    def setup_method(self):
        """Setup test bridge"""
        self.bridge = DesignerBridge()
    
    @pytest.mark.asyncio
    async def test_generate_ui_design(self):
        """Test UI design generation"""
        result = await self.bridge.generate_ui_design(
            prompt="Create a modern e-commerce interface",
            project_type="web"
        )
        
        assert result["success"] is True
        assert "design_files" in result
        assert "design_specifications" in result
        assert "figma_design" in result["design_files"]
        assert "color_palette" in result["design_specifications"]
    
    @pytest.mark.asyncio
    async def test_generate_brand_assets(self):
        """Test brand asset generation"""
        result = await self.bridge.generate_brand_assets(
            brand_brief="Tech startup focused on sustainability",
            industry="technology"
        )
        
        assert result["success"] is True
        assert "brand_assets" in result
        assert "visual_identity" in result
        assert "logo_variations" in result["brand_assets"]
        assert "primary_colors" in result["visual_identity"]
    
    @pytest.mark.asyncio
    async def test_create_prototype(self):
        """Test prototype creation"""
        result = await self.bridge.create_prototype(
            requirements="Mobile app for task management",
            fidelity="high"
        )
        
        assert result["success"] is True
        assert "prototype_files" in result
        assert "prototype_features" in result
        assert "uizard_prototype" in result["prototype_files"]
        assert "user_flows" in result["prototype_features"]
    
    @pytest.mark.asyncio
    async def test_generate_images(self):
        """Test AI image generation"""
        prompts = ["Modern office workspace", "Team collaboration"]
        result = await self.bridge.generate_images(prompts, style="professional")
        
        assert result["success"] is True
        assert "images" in result
        assert len(result["images"]) == 2
        assert "batch_metadata" in result
        assert result["batch_metadata"]["total_images"] == 2
    
    @pytest.mark.asyncio
    async def test_create_design_system(self):
        """Test design system creation"""
        result = await self.bridge.create_design_system(
            project_requirements="Enterprise SaaS application"
        )
        
        assert result["success"] is True
        assert "system_files" in result
        assert "system_components" in result
        assert "figma_library" in result["system_files"]
        assert "color_tokens" in result["system_components"]
    
    def test_color_palette_generation(self):
        """Test color palette generation"""
        palette = self.bridge._generate_color_palette({})
        
        assert "primary" in palette
        assert "secondary" in palette
        assert "background" in palette
        assert palette["primary"] == "#3B82F6"
    
    def test_typography_generation(self):
        """Test typography generation"""
        typography = self.bridge._generate_typography({})
        
        assert "heading_font" in typography
        assert "body_font" in typography
        assert "heading_sizes" in typography
        assert typography["heading_font"] == "Inter"
    
    def test_layout_system_generation(self):
        """Test layout system generation"""
        layout = self.bridge._generate_layout_system("web")
        
        assert "grid_system" in layout
        assert "max_width" in layout
        assert "breakpoints" in layout
        assert layout["grid_system"] == "12-column grid"


class TestDesignerIntegration:
    """Test Designer Agent integration"""
    
    def test_integration_imports(self):
        """Test that integration modules import correctly"""
        from agents.designer_integration import (
            register_designer_agent,
            get_designer_agent,
            get_designer_bridge,
            get_designer_prompt
        )
        
        agent = get_designer_agent()
        assert agent is not None
        assert isinstance(agent, DesignerAgent)
        
        bridge = get_designer_bridge()
        assert bridge is not None
        assert isinstance(bridge, DesignerBridge)
        
        prompt = get_designer_prompt("ui_design")
        assert prompt is not None
        assert len(prompt) > 100
    
    def test_designer_prompts(self):
        """Test designer prompt templates"""
        from agents.designer_integration import DESIGNER_PROMPTS
        
        assert "ui_design" in DESIGNER_PROMPTS
        assert "brand_design" in DESIGNER_PROMPTS
        assert "prototype" in DESIGNER_PROMPTS
        
        ui_prompt = DESIGNER_PROMPTS["ui_design"]
        assert "Figma AI" in ui_prompt
        assert "Uizard" in ui_prompt
        assert "design principles" in ui_prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
