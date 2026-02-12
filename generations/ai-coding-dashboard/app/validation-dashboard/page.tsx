'use client';

import { useState, useEffect } from 'react';
import { validateA2UIMessage } from '@/lib/a2ui-validator';
import { A2UIMessageType, A2UI_COMPONENT_TYPES } from '@/types/a2ui';

interface ValidationStats {
  totalValidations: number;
  passedValidations: number;
  failedValidations: number;
  catalogCompliance: number;
}

export default function ValidationDashboard() {
  const [jsonInput, setJsonInput] = useState('');
  const [validationResult, setValidationResult] = useState<any>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [stats, setStats] = useState<ValidationStats>({
    totalValidations: 0,
    passedValidations: 0,
    failedValidations: 0,
    catalogCompliance: 100,
  });

  const handleValidate = () => {
    if (!jsonInput.trim()) {
      setValidationResult({
        valid: false,
        errors: ['No JSON input provided'],
      });
      return;
    }

    try {
      const parsed = JSON.parse(jsonInput);
      const result = validateA2UIMessage(parsed);
      setValidationResult(result);

      // Update stats
      setStats((prev) => ({
        totalValidations: prev.totalValidations + 1,
        passedValidations: prev.passedValidations + (result.valid ? 1 : 0),
        failedValidations: prev.failedValidations + (result.valid ? 0 : 1),
        catalogCompliance: result.valid
          ? 100
          : Math.max(
              0,
              100 -
                (result.errors.filter((e: string) => e.includes('catalog')).length /
                  result.errors.length) *
                  100
            ),
      }));
    } catch (error) {
      setValidationResult({
        valid: false,
        errors: [`JSON Parse Error: ${(error as Error).message}`],
      });

      setStats((prev) => ({
        ...prev,
        totalValidations: prev.totalValidations + 1,
        failedValidations: prev.failedValidations + 1,
      }));
    }
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadedFile(file);

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      setJsonInput(content);
    };
    reader.readAsText(file);
  };

  const loadExample = (example: string) => {
    const examples: Record<string, any> = {
      validCard: {
        messageType: 'beginRendering',
        components: [
          {
            type: 'a2ui.Card',
            id: 'card-1',
            props: { title: 'Task Dashboard' },
            children: ['text-1', 'btn-1'],
          },
          {
            type: 'a2ui.Text',
            id: 'text-1',
            props: { content: 'You have 5 pending tasks' },
          },
          {
            type: 'a2ui.Button',
            id: 'btn-1',
            props: { text: 'View Tasks', variant: 'primary' },
          },
        ],
      },
      validGrid: {
        messageType: 'surfaceUpdate',
        components: [
          {
            type: 'a2ui.Grid',
            id: 'grid-1',
            props: { cols: '3', gap: '4' },
            children: ['badge-1', 'badge-2', 'badge-3'],
          },
          { type: 'a2ui.Badge', id: 'badge-1', props: { variant: 'success' } },
          { type: 'a2ui.Badge', id: 'badge-2', props: { variant: 'warning' } },
          { type: 'a2ui.Badge', id: 'badge-3', props: { variant: 'error' } },
        ],
      },
      invalidMissingType: {
        messageType: 'beginRendering',
        components: [{ id: 'component-1', props: {} }],
      },
      securityViolation: {
        messageType: 'beginRendering',
        components: [
          {
            type: 'a2ui.MaliciousComponent',
            id: 'hack-1',
            props: { inject: "<script>alert('xss')</script>" },
          },
        ],
      },
      circularReference: {
        messageType: 'beginRendering',
        components: [
          {
            type: 'a2ui.Container',
            id: 'c1',
            props: {},
            children: ['c2'],
          },
          {
            type: 'a2ui.Container',
            id: 'c2',
            props: {},
            children: ['c1'],
          },
        ],
      },
    };

    setJsonInput(JSON.stringify(examples[example], null, 2));
  };

  const clearAll = () => {
    setJsonInput('');
    setValidationResult(null);
    setUploadedFile(null);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">A2UI Validation Dashboard</h1>
          <p className="text-gray-400">
            Protocol v0.8 Compliance Checker & Security Validator
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Total Validations</div>
            <div className="text-3xl font-bold">{stats.totalValidations}</div>
          </div>
          <div className="bg-gray-800 border border-green-700 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Passed</div>
            <div className="text-3xl font-bold text-green-400">
              {stats.passedValidations}
            </div>
          </div>
          <div className="bg-gray-800 border border-red-700 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Failed</div>
            <div className="text-3xl font-bold text-red-400">
              {stats.failedValidations}
            </div>
          </div>
          <div className="bg-gray-800 border border-blue-700 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Catalog Compliance</div>
            <div className="text-3xl font-bold text-blue-400">
              {stats.catalogCompliance.toFixed(0)}%
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Input Section */}
          <div className="space-y-4">
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
              <h2 className="text-2xl font-bold mb-4">Input</h2>

              {/* File Upload */}
              <div className="mb-4">
                <label className="block text-sm font-semibold mb-2">
                  Upload JSON File
                </label>
                <input
                  type="file"
                  accept=".json"
                  onChange={handleFileUpload}
                  className="block w-full text-sm text-gray-400
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-lg file:border-0
                    file:text-sm file:font-semibold
                    file:bg-blue-600 file:text-white
                    hover:file:bg-blue-700 cursor-pointer"
                />
                {uploadedFile && (
                  <p className="text-xs text-gray-400 mt-2">
                    Loaded: {uploadedFile.name}
                  </p>
                )}
              </div>

              {/* JSON Textarea */}
              <div className="mb-4">
                <label className="block text-sm font-semibold mb-2">
                  A2UI JSON Message
                </label>
                <textarea
                  value={jsonInput}
                  onChange={(e) => setJsonInput(e.target.value)}
                  className="w-full h-80 p-4 bg-gray-900 border border-gray-700 rounded-lg font-mono text-sm"
                  placeholder='{"messageType": "beginRendering", "components": [...]}'
                />
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 mb-4">
                <button
                  onClick={handleValidate}
                  className="flex-1 px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold"
                >
                  Validate
                </button>
                <button
                  onClick={clearAll}
                  className="px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg font-semibold"
                >
                  Clear
                </button>
              </div>

              {/* Example Buttons */}
              <div>
                <p className="text-sm font-semibold mb-2">Load Example:</p>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => loadExample('validCard')}
                    className="px-3 py-2 bg-green-600 hover:bg-green-700 rounded text-sm"
                  >
                    Valid Card
                  </button>
                  <button
                    onClick={() => loadExample('validGrid')}
                    className="px-3 py-2 bg-green-600 hover:bg-green-700 rounded text-sm"
                  >
                    Valid Grid
                  </button>
                  <button
                    onClick={() => loadExample('invalidMissingType')}
                    className="px-3 py-2 bg-yellow-600 hover:bg-yellow-700 rounded text-sm"
                  >
                    Missing Type
                  </button>
                  <button
                    onClick={() => loadExample('securityViolation')}
                    className="px-3 py-2 bg-red-600 hover:bg-red-700 rounded text-sm"
                  >
                    Security Violation
                  </button>
                  <button
                    onClick={() => loadExample('circularReference')}
                    className="px-3 py-2 bg-orange-600 hover:bg-orange-700 rounded text-sm"
                  >
                    Circular Ref
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Results Section */}
          <div className="space-y-4">
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
              <h2 className="text-2xl font-bold mb-4">Validation Result</h2>

              {validationResult ? (
                <div className="space-y-4">
                  {/* Status Badge */}
                  <div
                    className={`p-4 rounded-lg ${
                      validationResult.valid
                        ? 'bg-green-900 border border-green-700'
                        : 'bg-red-900 border border-red-700'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-4 h-4 rounded-full ${
                          validationResult.valid ? 'bg-green-500' : 'bg-red-500'
                        }`}
                      />
                      <span className="font-semibold text-xl">
                        {validationResult.valid ? 'VALID' : 'INVALID'}
                      </span>
                    </div>
                  </div>

                  {/* Errors */}
                  {validationResult.errors && validationResult.errors.length > 0 && (
                    <div className="bg-gray-900 border border-red-700 rounded-lg p-4">
                      <h3 className="font-semibold text-red-400 mb-2 flex items-center gap-2">
                        <span className="bg-red-600 text-white px-2 py-0.5 rounded text-xs">
                          {validationResult.errors.length}
                        </span>
                        Errors
                      </h3>
                      <ul className="space-y-2 text-sm">
                        {validationResult.errors.map((error: string, i: number) => (
                          <li
                            key={i}
                            className="flex gap-2 text-red-300 bg-red-900/30 p-2 rounded"
                          >
                            <span className="text-red-500">•</span>
                            <span>{error}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Warnings */}
                  {validationResult.warnings && validationResult.warnings.length > 0 && (
                    <div className="bg-gray-900 border border-yellow-700 rounded-lg p-4">
                      <h3 className="font-semibold text-yellow-400 mb-2 flex items-center gap-2">
                        <span className="bg-yellow-600 text-white px-2 py-0.5 rounded text-xs">
                          {validationResult.warnings.length}
                        </span>
                        Warnings
                      </h3>
                      <ul className="space-y-2 text-sm">
                        {validationResult.warnings.map((warning: string, i: number) => (
                          <li
                            key={i}
                            className="flex gap-2 text-yellow-300 bg-yellow-900/30 p-2 rounded"
                          >
                            <span className="text-yellow-500">⚠</span>
                            <span>{warning}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Success Details */}
                  {validationResult.valid && validationResult.message && (
                    <div className="bg-gray-900 border border-green-700 rounded-lg p-4">
                      <h3 className="font-semibold text-green-400 mb-3">
                        Validation Details
                      </h3>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-400">Message Type:</span>
                          <span className="text-green-300 font-mono">
                            {validationResult.message.messageType}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">Component Count:</span>
                          <span className="text-green-300">
                            {validationResult.message.components.length}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-400 block mb-1">
                            Component Types:
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {[
                              ...new Set(
                                validationResult.message.components.map(
                                  (c: any) => c.type
                                )
                              ),
                            ].map((type: string) => (
                              <span
                                key={type}
                                className="text-xs bg-green-900/50 text-green-300 px-2 py-1 rounded"
                              >
                                {type}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-8 text-center text-gray-400">
                  <p className="mb-2">No validation performed yet</p>
                  <p className="text-sm">
                    Enter or upload A2UI JSON and click "Validate"
                  </p>
                </div>
              )}
            </div>

            {/* Catalog Reference */}
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
              <h3 className="text-xl font-bold mb-3">A2UI v0.8 Specification</h3>
              <div className="space-y-3 text-sm">
                <div>
                  <strong className="text-blue-400">Required Fields:</strong>
                  <div className="text-gray-300 mt-1 font-mono text-xs">
                    type, id, props
                  </div>
                </div>
                <div>
                  <strong className="text-blue-400">Message Types:</strong>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {Object.values(A2UIMessageType).map((type) => (
                      <span
                        key={type}
                        className="text-xs bg-blue-900/50 text-blue-300 px-2 py-1 rounded font-mono"
                      >
                        {type}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <strong className="text-blue-400">Registered Components:</strong>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {A2UI_COMPONENT_TYPES.map((type) => (
                      <span
                        key={type}
                        className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded font-mono"
                      >
                        {type}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <strong className="text-blue-400">Security:</strong>
                  <p className="text-gray-300 mt-1">
                    Only catalog components allowed (allowlist approach)
                  </p>
                </div>
                <div>
                  <strong className="text-blue-400">Structure:</strong>
                  <p className="text-gray-300 mt-1">
                    Flat list with ID references (LLM-friendly)
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
