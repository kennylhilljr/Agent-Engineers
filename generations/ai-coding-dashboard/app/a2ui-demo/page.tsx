'use client';

import { A2UIRenderer, getA2UIComponentNames } from '@/lib/a2ui-catalog';
import { useState } from 'react';

export default function A2UIDemoPage() {
  const [inputValue, setInputValue] = useState('');
  const [clickCount, setClickCount] = useState(0);
  const componentNames = getA2UIComponentNames();

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <A2UIRenderer component="a2ui.Container" props={{ maxWidth: 'max-w-6xl' }}>
        <A2UIRenderer component="a2ui.Text" props={{ variant: 'h1' }}>
          A2UI Catalog Demo
        </A2UIRenderer>

        <A2UIRenderer component="a2ui.Divider" />

        <A2UIRenderer component="a2ui.Text" props={{ variant: 'body', className: 'mb-6' }}>
          This page demonstrates the A2UIRenderer component rendering various components from the A2UI catalog.
        </A2UIRenderer>

        <A2UIRenderer component="a2ui.Grid" props={{ cols: '2', gap: '6', className: 'mb-8' }}>
          <A2UIRenderer component="a2ui.Card" props={{ title: 'Component Catalog' }}>
            <A2UIRenderer component="a2ui.Text" props={{ variant: 'body', className: 'mb-4' }}>
              Available components: {componentNames.length}
            </A2UIRenderer>
            <div className="space-y-2">
              {componentNames.map((name) => (
                <A2UIRenderer key={name} component="a2ui.Badge" props={{ variant: 'info' }}>
                  {name}
                </A2UIRenderer>
              ))}
            </div>
          </A2UIRenderer>

          <A2UIRenderer component="a2ui.Card" props={{ title: 'Interactive Demo' }}>
            <div className="space-y-4">
              <div>
                <A2UIRenderer component="a2ui.Text" props={{ variant: 'small', className: 'mb-2' }}>
                  Button with click counter:
                </A2UIRenderer>
                <A2UIRenderer
                  component="a2ui.Button"
                  props={{
                    onClick: () => setClickCount(clickCount + 1),
                    variant: 'primary',
                  }}
                >
                  Clicked {clickCount} times
                </A2UIRenderer>
              </div>

              <div>
                <A2UIRenderer component="a2ui.Text" props={{ variant: 'small', className: 'mb-2' }}>
                  Input field:
                </A2UIRenderer>
                <A2UIRenderer
                  component="a2ui.Input"
                  props={{
                    placeholder: 'Type something...',
                    value: inputValue,
                    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setInputValue(e.target.value),
                    className: 'w-full',
                  }}
                />
                {inputValue && (
                  <A2UIRenderer component="a2ui.Text" props={{ variant: 'caption', className: 'mt-2' }}>
                    You typed: {inputValue}
                  </A2UIRenderer>
                )}
              </div>
            </div>
          </A2UIRenderer>
        </A2UIRenderer>

        <A2UIRenderer component="a2ui.Card" props={{ title: 'Button Variants', className: 'mb-6' }}>
          <div className="flex flex-wrap gap-4">
            <A2UIRenderer component="a2ui.Button" props={{ variant: 'primary' }}>
              Primary
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Button" props={{ variant: 'secondary' }}>
              Secondary
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Button" props={{ variant: 'outline' }}>
              Outline
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Button" props={{ variant: 'danger' }}>
              Danger
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Button" props={{ disabled: true }}>
              Disabled
            </A2UIRenderer>
          </div>
        </A2UIRenderer>

        <A2UIRenderer component="a2ui.Card" props={{ title: 'Badge Variants', className: 'mb-6' }}>
          <div className="flex flex-wrap gap-4">
            <A2UIRenderer component="a2ui.Badge" props={{ variant: 'default' }}>
              Default
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Badge" props={{ variant: 'success' }}>
              Success
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Badge" props={{ variant: 'warning' }}>
              Warning
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Badge" props={{ variant: 'error' }}>
              Error
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Badge" props={{ variant: 'info' }}>
              Info
            </A2UIRenderer>
          </div>
        </A2UIRenderer>

        <A2UIRenderer component="a2ui.Card" props={{ title: 'Text Variants', className: 'mb-6' }}>
          <div className="space-y-3">
            <A2UIRenderer component="a2ui.Text" props={{ variant: 'h1' }}>
              Heading 1
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Text" props={{ variant: 'h2' }}>
              Heading 2
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Text" props={{ variant: 'h3' }}>
              Heading 3
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Text" props={{ variant: 'h4' }}>
              Heading 4
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Text" props={{ variant: 'body' }}>
              Body text - This is the default text variant.
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Text" props={{ variant: 'small' }}>
              Small text - Slightly smaller than body text.
            </A2UIRenderer>
            <A2UIRenderer component="a2ui.Text" props={{ variant: 'caption' }}>
              Caption text - The smallest text variant with gray color.
            </A2UIRenderer>
          </div>
        </A2UIRenderer>

        <A2UIRenderer component="a2ui.Card" props={{ title: 'Error Handling', className: 'mb-6' }}>
          <A2UIRenderer component="a2ui.Text" props={{ variant: 'body', className: 'mb-4' }}>
            When an invalid component name is provided, the renderer displays an error:
          </A2UIRenderer>
          <A2UIRenderer component="a2ui.NonExistentComponent">
            This should show an error message
          </A2UIRenderer>
        </A2UIRenderer>

        <A2UIRenderer component="a2ui.Divider" />

        <A2UIRenderer component="a2ui.Text" props={{ variant: 'caption', className: 'text-center' }}>
          KAN-111: A2UI Catalog Registration - All components rendered via A2UIRenderer
        </A2UIRenderer>
      </A2UIRenderer>
    </div>
  );
}
