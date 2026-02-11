import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

/**
 * KAN-47: Initialize Next.js project with TypeScript and Tailwind
 *
 * This test suite verifies all requirements for project initialization:
 * 1. Next.js 14+ is installed
 * 2. TypeScript is enabled and configured
 * 3. Tailwind CSS is configured with dark theme
 * 4. CopilotKit packages are installed
 * 5. Dev server is configured to run on port 3010
 */

describe('KAN-47: Project Initialization', () => {
  const projectRoot = path.resolve(__dirname, '..');

  describe('package.json configuration', () => {
    let packageJson: any;

    it('should have valid package.json', () => {
      const packagePath = path.join(projectRoot, 'package.json');
      expect(fs.existsSync(packagePath)).toBe(true);

      const content = fs.readFileSync(packagePath, 'utf-8');
      packageJson = JSON.parse(content);
      expect(packageJson).toBeDefined();
    });

    it('should have Next.js version 14 or higher', () => {
      const packagePath = path.join(projectRoot, 'package.json');
      const content = fs.readFileSync(packagePath, 'utf-8');
      packageJson = JSON.parse(content);

      expect(packageJson.dependencies.next).toBeDefined();
      const version = packageJson.dependencies.next.replace(/[\^~]/, '');
      const majorVersion = parseInt(version.split('.')[0], 10);
      expect(majorVersion).toBeGreaterThanOrEqual(14);
    });

    it('should have CopilotKit core package installed', () => {
      const packagePath = path.join(projectRoot, 'package.json');
      const content = fs.readFileSync(packagePath, 'utf-8');
      packageJson = JSON.parse(content);

      expect(packageJson.dependencies['@copilotkit/react-core']).toBeDefined();
    });

    it('should have CopilotKit UI package installed', () => {
      const packagePath = path.join(projectRoot, 'package.json');
      const content = fs.readFileSync(packagePath, 'utf-8');
      packageJson = JSON.parse(content);

      expect(packageJson.dependencies['@copilotkit/react-ui']).toBeDefined();
    });

    it('should have dev script configured for port 3010', () => {
      const packagePath = path.join(projectRoot, 'package.json');
      const content = fs.readFileSync(packagePath, 'utf-8');
      packageJson = JSON.parse(content);

      expect(packageJson.scripts.dev).toContain('-p 3010');
    });

    it('should have start script configured for port 3010', () => {
      const packagePath = path.join(projectRoot, 'package.json');
      const content = fs.readFileSync(packagePath, 'utf-8');
      packageJson = JSON.parse(content);

      expect(packageJson.scripts.start).toContain('-p 3010');
    });

    it('should have React 18+ installed', () => {
      const packagePath = path.join(projectRoot, 'package.json');
      const content = fs.readFileSync(packagePath, 'utf-8');
      packageJson = JSON.parse(content);

      expect(packageJson.dependencies.react).toBeDefined();
      const version = packageJson.dependencies.react.replace(/[\^~]/, '');
      const majorVersion = parseInt(version.split('.')[0], 10);
      expect(majorVersion).toBeGreaterThanOrEqual(18);
    });

    it('should have Tailwind CSS in devDependencies', () => {
      const packagePath = path.join(projectRoot, 'package.json');
      const content = fs.readFileSync(packagePath, 'utf-8');
      packageJson = JSON.parse(content);

      expect(packageJson.devDependencies.tailwindcss).toBeDefined();
    });

    it('should have TypeScript in devDependencies', () => {
      const packagePath = path.join(projectRoot, 'package.json');
      const content = fs.readFileSync(packagePath, 'utf-8');
      packageJson = JSON.parse(content);

      expect(packageJson.devDependencies.typescript).toBeDefined();
    });
  });

  describe('TypeScript configuration', () => {
    let tsConfig: any;

    it('should have tsconfig.json', () => {
      const tsConfigPath = path.join(projectRoot, 'tsconfig.json');
      expect(fs.existsSync(tsConfigPath)).toBe(true);

      const content = fs.readFileSync(tsConfigPath, 'utf-8');
      tsConfig = JSON.parse(content);
      expect(tsConfig).toBeDefined();
    });

    it('should have strict mode enabled', () => {
      const tsConfigPath = path.join(projectRoot, 'tsconfig.json');
      const content = fs.readFileSync(tsConfigPath, 'utf-8');
      tsConfig = JSON.parse(content);

      expect(tsConfig.compilerOptions.strict).toBe(true);
    });

    it('should have jsx preserve for Next.js', () => {
      const tsConfigPath = path.join(projectRoot, 'tsconfig.json');
      const content = fs.readFileSync(tsConfigPath, 'utf-8');
      tsConfig = JSON.parse(content);

      expect(tsConfig.compilerOptions.jsx).toBe('preserve');
    });

    it('should include Next.js plugin', () => {
      const tsConfigPath = path.join(projectRoot, 'tsconfig.json');
      const content = fs.readFileSync(tsConfigPath, 'utf-8');
      tsConfig = JSON.parse(content);

      expect(tsConfig.compilerOptions.plugins).toBeDefined();
      const hasNextPlugin = tsConfig.compilerOptions.plugins.some(
        (p: any) => p.name === 'next'
      );
      expect(hasNextPlugin).toBe(true);
    });

    it('should have path alias configured', () => {
      const tsConfigPath = path.join(projectRoot, 'tsconfig.json');
      const content = fs.readFileSync(tsConfigPath, 'utf-8');
      tsConfig = JSON.parse(content);

      expect(tsConfig.compilerOptions.paths).toBeDefined();
      expect(tsConfig.compilerOptions.paths['@/*']).toBeDefined();
    });
  });

  describe('Tailwind CSS configuration', () => {
    let tailwindConfig: string;

    it('should have tailwind.config.ts', () => {
      const tailwindPath = path.join(projectRoot, 'tailwind.config.ts');
      expect(fs.existsSync(tailwindPath)).toBe(true);

      tailwindConfig = fs.readFileSync(tailwindPath, 'utf-8');
      expect(tailwindConfig).toBeDefined();
    });

    it('should have dark mode configured as class', () => {
      const tailwindPath = path.join(projectRoot, 'tailwind.config.ts');
      tailwindConfig = fs.readFileSync(tailwindPath, 'utf-8');

      expect(tailwindConfig).toContain('darkMode');
      expect(tailwindConfig).toContain('"class"');
    });

    it('should have content paths for app directory', () => {
      const tailwindPath = path.join(projectRoot, 'tailwind.config.ts');
      tailwindConfig = fs.readFileSync(tailwindPath, 'utf-8');

      expect(tailwindConfig).toContain('./app/**/*.{js,ts,jsx,tsx,mdx}');
    });

    it('should have content paths for components directory', () => {
      const tailwindPath = path.join(projectRoot, 'tailwind.config.ts');
      tailwindConfig = fs.readFileSync(tailwindPath, 'utf-8');

      expect(tailwindConfig).toContain('./components/**/*.{js,ts,jsx,tsx,mdx}');
    });

    it('should export Config type for TypeScript', () => {
      const tailwindPath = path.join(projectRoot, 'tailwind.config.ts');
      tailwindConfig = fs.readFileSync(tailwindPath, 'utf-8');

      expect(tailwindConfig).toContain('import type { Config }');
      expect(tailwindConfig).toContain('from "tailwindcss"');
    });

    it('should have postcss.config.mjs for Tailwind processing', () => {
      const postcssPath = path.join(projectRoot, 'postcss.config.mjs');
      expect(fs.existsSync(postcssPath)).toBe(true);
    });
  });

  describe('Next.js App Router configuration', () => {
    it('should have app directory', () => {
      const appPath = path.join(projectRoot, 'app');
      expect(fs.existsSync(appPath)).toBe(true);
      expect(fs.statSync(appPath).isDirectory()).toBe(true);
    });

    it('should have app/layout.tsx for root layout', () => {
      const layoutPath = path.join(projectRoot, 'app', 'layout.tsx');
      expect(fs.existsSync(layoutPath)).toBe(true);
    });

    it('should have app/page.tsx for home page', () => {
      const pagePath = path.join(projectRoot, 'app', 'page.tsx');
      expect(fs.existsSync(pagePath)).toBe(true);
    });

    it('should have app/globals.css with Tailwind directives', () => {
      const globalsCssPath = path.join(projectRoot, 'app', 'globals.css');
      expect(fs.existsSync(globalsCssPath)).toBe(true);

      const content = fs.readFileSync(globalsCssPath, 'utf-8');
      expect(content).toContain('@tailwind base');
      expect(content).toContain('@tailwind components');
      expect(content).toContain('@tailwind utilities');
    });

    it('should have next.config.mjs', () => {
      const nextConfigPath = path.join(projectRoot, 'next.config.mjs');
      expect(fs.existsSync(nextConfigPath)).toBe(true);
    });
  });

  describe('Project structure', () => {
    it('should have .gitignore', () => {
      const gitignorePath = path.join(projectRoot, '.gitignore');
      expect(fs.existsSync(gitignorePath)).toBe(true);
    });

    it('should have README.md', () => {
      const readmePath = path.join(projectRoot, 'README.md');
      expect(fs.existsSync(readmePath)).toBe(true);
    });

    it('should have node_modules installed', () => {
      const nodeModulesPath = path.join(projectRoot, 'node_modules');
      expect(fs.existsSync(nodeModulesPath)).toBe(true);
      expect(fs.statSync(nodeModulesPath).isDirectory()).toBe(true);
    });

    it('should have .next build directory (or will be created on build)', () => {
      // This might not exist until first build, so we just check that the build script exists
      const packagePath = path.join(projectRoot, 'package.json');
      const content = fs.readFileSync(packagePath, 'utf-8');
      const packageJson = JSON.parse(content);
      expect(packageJson.scripts.build).toBe('next build');
    });
  });

  describe('CopilotKit integration readiness', () => {
    it('should have both CopilotKit packages with compatible versions', () => {
      const packagePath = path.join(projectRoot, 'package.json');
      const content = fs.readFileSync(packagePath, 'utf-8');
      const packageJson = JSON.parse(content);

      const coreVersion = packageJson.dependencies['@copilotkit/react-core'];
      const uiVersion = packageJson.dependencies['@copilotkit/react-ui'];

      expect(coreVersion).toBeDefined();
      expect(uiVersion).toBeDefined();

      // Verify they are similar versions (both should be 1.x.x)
      const coreClean = coreVersion.replace(/[\^~]/, '');
      const uiClean = uiVersion.replace(/[\^~]/, '');
      const coreMajor = parseInt(coreClean.split('.')[0], 10);
      const uiMajor = parseInt(uiClean.split('.')[0], 10);

      expect(coreMajor).toBe(uiMajor);
    });
  });
});
