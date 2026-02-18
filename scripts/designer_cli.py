#!/usr/bin/env python3
"""
Designer Agent CLI
==================

Command-line interface for the Designer Agent.
"""

import asyncio
import json
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.designer_agent import designer_agent
from bridges.designer_bridge import DesignerBridge


async def generate_ui_design(prompt: str, project_type: str, output_dir: str):
    """Generate UI design and save results"""
    bridge = DesignerBridge()
    result = await bridge.generate_ui_design(prompt, project_type)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save design specifications
    design_file = output_path / f"ui_design_{project_type}.json"
    with open(design_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"✅ UI Design Generated: {design_file}")
    print(f"📁 Design files: {len(result['design_files'])}")
    print(f"🎨 Color palette: {len(result['design_specifications']['color_palette'])} colors")


async def generate_brand_assets(brand_brief: str, industry: str, output_dir: str):
    """Generate brand assets and save results"""
    bridge = DesignerBridge()
    result = await bridge.generate_brand_assets(brand_brief, industry)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save brand specifications
    brand_file = output_path / f"brand_assets_{industry}.json"
    with open(brand_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"✅ Brand Assets Generated: {brand_file}")
    print(f"📁 Asset files: {len(result['brand_assets'])}")
    print(f"🎨 Color system: {len(result['visual_identity']['primary_colors'])} colors")


async def create_prototype(requirements: str, fidelity: str, output_dir: str):
    """Create prototype and save results"""
    bridge = DesignerBridge()
    result = await bridge.create_prototype(requirements, fidelity)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save prototype specifications
    prototype_file = output_path / f"prototype_{fidelity}.json"
    with open(prototype_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"✅ Prototype Created: {prototype_file}")
    print(f"📁 Prototype files: {len(result['prototype_files'])}")
    print(f"🔄 User flows: {len(result['prototype_features']['user_flows'])}")


async def generate_images(prompts: list, style: str, output_dir: str):
    """Generate images and save results"""
    bridge = DesignerBridge()
    result = await bridge.generate_images(prompts, style)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save image specifications
    images_file = output_path / f"images_{style}.json"
    with open(images_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"✅ Images Generated: {images_file}")
    print(f"🖼️ Total images: {result['batch_metadata']['total_images']}")
    print(f"🎨 Style: {style}")


async def create_design_system(project_requirements: str, output_dir: str):
    """Create design system and save results"""
    bridge = DesignerBridge()
    result = await bridge.create_design_system(project_requirements)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save design system specifications
    system_file = output_path / "design_system.json"
    with open(system_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"✅ Design System Created: {system_file}")
    print(f"📁 System files: {len(result['system_files'])}")
    print(f"🧩 Components: {len(result['system_components']['component_library'])}")


def show_agent_info():
    """Display designer agent information"""
    print(designer_agent.get_expertise_summary())
    
    print("\n🛠️  Primary AI Tools:")
    for tool in designer_agent.primary_tools:
        print(f"  • {tool.value.replace('_', ' ').title()}")
    
    print("\n🎯 Specializations:")
    for spec in designer_agent.specialization:
        print(f"  • {spec.value.replace('_', ' ').title()}")
    
    print("\n💼 Capabilities:")
    for cap in designer_agent.capabilities:
        print(f"  • {cap.name}: {cap.revenue_impact}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Designer Agent CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # UI Design command
    ui_parser = subparsers.add_parser('ui-design', help='Generate UI design')
    ui_parser.add_argument('prompt', help='Design prompt')
    ui_parser.add_argument('--type', default='web', choices=['web', 'mobile'], help='Project type')
    ui_parser.add_argument('--output', default='./designs', help='Output directory')
    
    # Brand Design command
    brand_parser = subparsers.add_parser('brand-design', help='Generate brand assets')
    brand_parser.add_argument('brief', help='Brand brief')
    brand_parser.add_argument('--industry', default='technology', help='Industry type')
    brand_parser.add_argument('--output', default='./brand', help='Output directory')
    
    # Prototype command
    prototype_parser = subparsers.add_parser('prototype', help='Create prototype')
    prototype_parser.add_argument('requirements', help='Prototype requirements')
    prototype_parser.add_argument('--fidelity', default='high', choices=['low', 'medium', 'high'], help='Prototype fidelity')
    prototype_parser.add_argument('--output', default='./prototypes', help='Output directory')
    
    # Image Generation command
    image_parser = subparsers.add_parser('images', help='Generate images')
    image_parser.add_argument('prompts', nargs='+', help='Image prompts')
    image_parser.add_argument('--style', default='professional', help='Image style')
    image_parser.add_argument('--output', default='./images', help='Output directory')
    
    # Design System command
    system_parser = subparsers.add_parser('design-system', help='Create design system')
    system_parser.add_argument('requirements', help='Project requirements')
    system_parser.add_argument('--output', default='./design-system', help='Output directory')
    
    # Info command
    subparsers.add_parser('info', help='Show agent information')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'info':
        show_agent_info()
        return
    
    # Execute commands
    if args.command == 'ui-design':
        asyncio.run(generate_ui_design(args.prompt, args.type, args.output))
    elif args.command == 'brand-design':
        asyncio.run(generate_brand_assets(args.brief, args.industry, args.output))
    elif args.command == 'prototype':
        asyncio.run(create_prototype(args.requirements, args.fidelity, args.output))
    elif args.command == 'images':
        asyncio.run(generate_images(args.prompts, args.style, args.output))
    elif args.command == 'design-system':
        asyncio.run(create_design_system(args.requirements, args.output))


if __name__ == "__main__":
    main()
