/**
 * A2UI Type Definitions
 * Core types for the Agent-to-UI component system
 */

import React from 'react';

/**
 * Event types that A2UI components can emit
 */
export enum A2UIEventType {
  CLICK = 'click',
  SUBMIT = 'submit',
  CANCEL = 'cancel',
  APPROVE = 'approve',
  REJECT = 'reject',
  EXPAND = 'expand',
  COLLAPSE = 'collapse',
  SELECT = 'select',
  CHANGE = 'change',
}

/**
 * Message types for A2UI component communication
 */
export enum A2UIMessageType {
  COMMAND = 'command',
  QUERY = 'query',
  NOTIFICATION = 'notification',
  ERROR = 'error',
  SUCCESS = 'success',
}

/**
 * Base props interface that all A2UI components receive
 */
export interface A2UIProps {
  type: string;
  data: Record<string, any>;
  metadata?: {
    componentId?: string;
    timestamp?: string;
    source?: string;
    [key: string]: any;
  };
  onEvent?: (eventType: A2UIEventType, payload?: any) => void;
}

/**
 * A2UI Component interface - all catalog components must implement this
 */
export interface A2UIComponent {
  (props: A2UIProps): JSX.Element;
}

/**
 * Catalog type - maps component type strings to React components
 */
export type A2UICatalog = Record<string, A2UIComponent>;

/**
 * Valid A2UI component type strings
 */
export type A2UIComponentType =
  | 'a2ui.TaskCard'
  | 'a2ui.ProgressRing'
  | 'a2ui.FileTree'
  | 'a2ui.TestResults'
  | 'a2ui.ActivityItem'
  | 'a2ui.ApprovalCard'
  | 'a2ui.DecisionCard'
  | 'a2ui.MilestoneCard'
  | 'a2ui.ErrorCard';

/**
 * Component-specific prop types
 */
export interface TaskCardData {
  title: string;
  status: 'pending' | 'in-progress' | 'completed' | 'failed';
  assignee?: string;
  priority?: 'low' | 'medium' | 'high' | 'critical';
  dueDate?: string;
  description?: string;
}

export interface ProgressRingData {
  percentage: number;
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  color?: string;
}

export interface FileTreeData {
  nodes: FileNode[];
  expandedPaths?: string[];
  selectedPath?: string;
}

export interface FileNode {
  path: string;
  name: string;
  type: 'file' | 'directory';
  children?: FileNode[];
}

export interface TestResultsData {
  totalTests: number;
  passedTests: number;
  failedTests: number;
  skippedTests?: number;
  duration?: number;
  testCases?: TestCase[];
}

export interface TestCase {
  name: string;
  status: 'passed' | 'failed' | 'skipped';
  duration?: number;
  error?: string;
}

export interface ActivityItemData {
  actor: string;
  action: string;
  target?: string;
  timestamp: string;
  icon?: string;
}

export interface ApprovalCardData {
  title: string;
  description: string;
  requester: string;
  requestedAt: string;
  approvers?: string[];
  status?: 'pending' | 'approved' | 'rejected';
}

export interface DecisionCardData {
  question: string;
  options: DecisionOption[];
  selectedOption?: string;
  description?: string;
}

export interface DecisionOption {
  id: string;
  label: string;
  description?: string;
}

export interface MilestoneCardData {
  title: string;
  status: 'upcoming' | 'in-progress' | 'completed' | 'missed';
  dueDate: string;
  progress?: number;
  tasks?: {
    total: number;
    completed: number;
  };
}

export interface ErrorCardData {
  message: string;
  code?: string;
  details?: string;
  timestamp?: string;
  stackTrace?: string;
}
