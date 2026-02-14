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
  (props: A2UIProps): React.JSX.Element;
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
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
  category?: 'setup' | 'backend' | 'frontend' | 'a2ui-catalog' | 'feature' | 'testing' | 'styling';
  progress?: number; // 0-100
  assignee?: string;
  dueDate?: string;
  description?: string;
}

export interface ProgressRingData {
  percentage: number;
  tasksCompleted?: number;
  filesModified?: number;
  testsCompleted?: number;
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
  modified?: boolean;
}

export interface TestResultsData {
  testId: string;
  title: string;
  status: 'pending' | 'running' | 'passed' | 'failed';
  totalTests: number;
  passedTests: number;
  failedTests: number;
  skippedTests?: number;
  duration?: number;
  testCases?: TestCase[];
  testSuites?: TestSuite[];
  logs?: string[];
  showDetails?: boolean;
  onStatusChange?: (status: string) => void;
}

export interface TestCase {
  name: string;
  status: 'passed' | 'failed' | 'skipped' | 'running';
  duration?: number;
  error?: string;
  suite?: string;
}

export interface TestSuite {
  name: string;
  status?: 'passed' | 'failed' | 'pending';
  total?: number;
  passed: number;
  failed: number;
  skipped?: number;
  duration?: number;
  tests: TestCase[] | number;
}

export interface ActivityItemData {
  actor: string;
  action: string;
  target?: string;
  timestamp: string;
  icon?: string;
}

export interface ApprovalCardData {
  approvalId: string;
  title: string;
  description: string;
  context?: string;
  action: string; // What action needs approval (e.g., "Delete database table", "Deploy to production")
  severity?: 'low' | 'medium' | 'high' | 'critical'; // default: 'medium'
  requiredApproval?: boolean; // Must approve to proceed (default: true)
  metadata?: Record<string, any>;
  approvalOptions?: Array<{ label: string; value: string }>;
  onApprove?: (reason?: string) => void;
  onReject?: (reason?: string) => void;
  onRespond?: (response: { approved: boolean; reason?: string }) => void;
  status?: 'pending' | 'approved' | 'rejected'; // default: 'pending'
  loading?: boolean;
  deadline?: string; // ISO date string
  // Legacy support
  requester?: string;
  requestedAt?: string;
  approvers?: string[];
}

export interface DecisionCardData {
  decisionId: string;
  question: string; // The decision question/prompt
  options: DecisionOption[];
  context?: string; // Additional context
  recommendation?: string; // AI recommendation text
  status?: 'pending' | 'decided' | 'timeout' | 'skipped' | 'cancelled';
  selectedOptionId?: string;
  onSelect?: (optionId: string) => void;
  onRespond?: (response: { optionId: string; reasoning?: string }) => void;
  loading?: boolean;
  reasoningVisible?: boolean;
}

export interface DecisionOption {
  id: string;
  label: string;
  description?: string;
  recommended?: boolean; // Visual indicator
}

export interface MilestoneCardData {
  milestoneId: string;
  title: string;
  summary: string;
  tasksCompleted: number;
  totalTasks: number;
  nextPhase?: string;
  completionDate?: Date;
  celebrationMessage?: string;
  celebrationAnimation?: boolean; // default: true
}

export interface ErrorCardData {
  message: string;
  code?: string;
  details?: string;
  timestamp?: string;
  stackTrace?: string;
}
