'use client';

import { useState } from 'react';
import { validateA2UIMessage } from '@/lib/a2ui-validator';
import { A2UIMessageType } from '@/types/a2ui';

export default function A2UIValidatorDemo() {
  const [jsonInput, setJsonInput] = useState(`{
  "messageType": "beginRendering",
  "components": [
    {
      "type": "a2ui.Card",
      "id": "card-1",
      "props": {
        "title": "A2UI Validator Demo"
      },
      "children": ["text-1", "btn-1"]
    },
    {
      "type": "a2ui.Text",
      "id": "text-1",
      "props": {
        "content": "This validates A2UI protocol v0.8 compliance"
      }
    },
    {
      "type": "a2ui.Button",
      "id": "btn-1",
      "props": {
        "text": "Test Button"
      }
    }
  ]
}`);

  const [validationResult, setValidationResult] = useState<any>(null);

  const handleValidate = () => {
    try {
      const parsed = JSON.parse(jsonInput);
      const result = validateA2UIMessage(parsed);
      setValidationResult(result);
    } catch (error) {
      setValidationResult({
        valid: false,
        errors: [`JSON Parse Error: ${(error as Error).message}`],
      });
    }
  };

  const loadExample = (example: string) => {
    const examples: Record<string, string> = {
      valid: `{
  "messageType": "beginRendering",
  "components": [
    {
      "type": "a2ui.Button",
      "id": "btn-1",
      "props": { "text": "Valid Button" }
    }
  ]
}`,
      missingType: `{
  "messageType": "beginRendering",
  "components": [
    {
      "id": "component-1",
      "props": {}
    }
  ]
}`,
      invalidType: `{
  "messageType": "beginRendering",
  "components": [
    {
      "type": "a2ui.MaliciousComponent",
      "id": "hack-1",
      "props": {}
    }
  ]
}`,
      circular: `{
  "messageType": "beginRendering",
  "components": [
    {
      "type": "a2ui.Container",
      "id": "c1",
      "props": {},
      "children": ["c2"]
    },
    {
      "type": "a2ui.Container",
      "id": "c2",
      "props": {},
      "children": ["c1"]
    }
  ]
}`,
    };

    setJsonInput(examples[example]);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold mb-2">A2UI Protocol Validator</h1>
        <p className="text-gray-400 mb-8">v0.8 Specification Compliance Checker</p>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Input Section */}
          <div>
            <div className="mb-4">
              <label className="block text-sm font-semibold mb-2">
                A2UI JSON Message
              </label>
              <textarea
                value={jsonInput}
                onChange={(e) => setJsonInput(e.target.value)}
                className="w-full h-96 p-4 bg-gray-800 border border-gray-700 rounded-lg font-mono text-sm"
                placeholder="Enter A2UI JSON message..."
              />
            </div>

            <div className="flex gap-2 mb-4 flex-wrap">
              <button
                onClick={() => loadExample('valid')}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm"
              >
                Valid Example
              </button>
              <button
                onClick={() => loadExample('missingType')}
                className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg text-sm"
              >
                Missing Type
              </button>
              <button
                onClick={() => loadExample('invalidType')}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-sm"
              >
                Invalid Type (Security)
              </button>
              <button
                onClick={() => loadExample('circular')}
                className="px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded-lg text-sm"
              >
                Circular Reference
              </button>
            </div>

            <button
              onClick={handleValidate}
              className="w-full px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold"
            >
              Validate Message
            </button>
          </div>

          {/* Results Section */}
          <div>
            <h2 className="text-2xl font-bold mb-4">Validation Result</h2>

            {validationResult ? (
              <div className="space-y-4">
                {/* Status */}
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
                      {validationResult.valid ? 'VALID ✓' : 'INVALID ✗'}
                    </span>
                  </div>
                </div>

                {/* Errors */}
                {validationResult.errors && validationResult.errors.length > 0 && (
                  <div className="bg-gray-800 border border-red-700 rounded-lg p-4">
                    <h3 className="font-semibold text-red-400 mb-2">
                      Errors ({validationResult.errors.length})
                    </h3>
                    <ul className="list-disc list-inside space-y-1 text-sm">
                      {validationResult.errors.map((error: string, i: number) => (
                        <li key={i} className="text-red-300">
                          {error}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Warnings */}
                {validationResult.warnings && validationResult.warnings.length > 0 && (
                  <div className="bg-gray-800 border border-yellow-700 rounded-lg p-4">
                    <h3 className="font-semibold text-yellow-400 mb-2">
                      Warnings ({validationResult.warnings.length})
                    </h3>
                    <ul className="list-disc list-inside space-y-1 text-sm">
                      {validationResult.warnings.map((warning: string, i: number) => (
                        <li key={i} className="text-yellow-300">
                          {warning}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Success Details */}
                {validationResult.valid && validationResult.message && (
                  <div className="bg-gray-800 border border-green-700 rounded-lg p-4">
                    <h3 className="font-semibold text-green-400 mb-2">
                      Validation Details
                    </h3>
                    <div className="text-sm space-y-1">
                      <p>
                        <span className="text-gray-400">Message Type:</span>{' '}
                        <span className="text-green-300">
                          {validationResult.message.messageType}
                        </span>
                      </p>
                      <p>
                        <span className="text-gray-400">Components:</span>{' '}
                        <span className="text-green-300">
                          {validationResult.message.components.length}
                        </span>
                      </p>
                      <p>
                        <span className="text-gray-400">Component Types:</span>{' '}
                        <span className="text-green-300">
                          {[
                            ...new Set(
                              validationResult.message.components.map(
                                (c: any) => c.type
                              )
                            ),
                          ].join(', ')}
                        </span>
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-gray-800 border border-gray-700 rounded-lg p-8 text-center text-gray-400">
                Enter A2UI JSON and click "Validate Message" to see results
              </div>
            )}

            {/* Spec Reference */}
            <div className="mt-8 bg-gray-800 border border-gray-700 rounded-lg p-4">
              <h3 className="font-semibold mb-2">A2UI v0.8 Spec</h3>
              <div className="text-sm space-y-2 text-gray-300">
                <p>
                  <strong>Required Fields:</strong> type, id, props
                </p>
                <p>
                  <strong>Message Types:</strong> beginRendering, surfaceUpdate,
                  dataModelUpdate
                </p>
                <p>
                  <strong>Security:</strong> Only catalog components allowed
                </p>
                <p>
                  <strong>Structure:</strong> Flat list with ID references
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
