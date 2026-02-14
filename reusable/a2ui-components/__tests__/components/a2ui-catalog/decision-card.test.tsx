import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DecisionCard } from '@/components/a2ui-catalog/decision-card';
import { A2UIEventType, DecisionCardData } from '@/lib/a2ui-types';

describe('DecisionCard Component', () => {
  const mockOnEvent = jest.fn();
  const mockOnSelect = jest.fn();
  const mockOnRespond = jest.fn();

  const baseData: DecisionCardData = {
    decisionId: 'dec-123',
    question: 'Which database should we use for this feature?',
    options: [
      {
        id: 'postgres',
        label: 'PostgreSQL',
        description: 'Relational database with ACID compliance',
        recommended: true,
      },
      {
        id: 'mongodb',
        label: 'MongoDB',
        description: 'Document database with flexible schema',
      },
      {
        id: 'redis',
        label: 'Redis',
        description: 'In-memory key-value store',
      },
    ],
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Basic Rendering', () => {
    it('should render decision card with question', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('decision-card')).toBeInTheDocument();
      expect(screen.getByTestId('decision-question')).toHaveTextContent(
        'Which database should we use for this feature?'
      );
    });

    it('should render all options', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('options-section')).toBeInTheDocument();
      expect(screen.getByTestId('option-postgres')).toBeInTheDocument();
      expect(screen.getByTestId('option-mongodb')).toBeInTheDocument();
      expect(screen.getByTestId('option-redis')).toBeInTheDocument();
    });

    it('should render option labels and descriptions', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('option-label-postgres')).toHaveTextContent('PostgreSQL');
      expect(screen.getByTestId('option-description-postgres')).toHaveTextContent(
        'Relational database with ACID compliance'
      );
    });

    it('should render without description for options without it', () => {
      const dataWithoutDescriptions: DecisionCardData = {
        ...baseData,
        options: [
          { id: 'opt1', label: 'Option 1' },
          { id: 'opt2', label: 'Option 2' },
        ],
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithoutDescriptions}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('option-description-opt1')).not.toBeInTheDocument();
      expect(screen.queryByTestId('option-description-opt2')).not.toBeInTheDocument();
    });

    it('should render context section when context is provided', () => {
      const dataWithContext = {
        ...baseData,
        context: 'This feature requires strong consistency and relational queries.',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithContext}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('context-section')).toBeInTheDocument();
      expect(screen.getByTestId('context-text')).toHaveTextContent(
        'This feature requires strong consistency and relational queries.'
      );
    });

    it('should not render context section when context is not provided', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('context-section')).not.toBeInTheDocument();
    });
  });

  describe('Recommendation Section', () => {
    it('should render recommendation section when recommendation is provided', () => {
      const dataWithRecommendation = {
        ...baseData,
        recommendation: 'PostgreSQL is recommended for its reliability and transaction support.',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithRecommendation}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('recommendation-section')).toBeInTheDocument();
      expect(screen.getByTestId('recommendation-icon')).toBeInTheDocument();
      expect(screen.getByTestId('recommendation-text')).toHaveTextContent(
        'PostgreSQL is recommended for its reliability and transaction support.'
      );
    });

    it('should not render recommendation section when recommendation is not provided', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('recommendation-section')).not.toBeInTheDocument();
    });

    it('should show recommended badge on recommended option', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('recommended-badge-postgres')).toBeInTheDocument();
      expect(screen.queryByTestId('recommended-badge-mongodb')).not.toBeInTheDocument();
      expect(screen.queryByTestId('recommended-badge-redis')).not.toBeInTheDocument();
    });
  });

  describe('Status States', () => {
    it('should display pending status badge by default', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      const card = screen.getByTestId('decision-card');
      expect(card.getAttribute('data-status')).toBe('pending');
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Pending Decision');
    });

    it('should display decided status badge when status is decided', () => {
      const decidedData = {
        ...baseData,
        status: 'decided' as const,
        selectedOptionId: 'postgres',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={decidedData}
          onEvent={mockOnEvent}
        />
      );

      const card = screen.getByTestId('decision-card');
      expect(card.getAttribute('data-status')).toBe('decided');
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Decided');
    });

    it('should display timeout status badge when status is timeout', () => {
      const timeoutData = {
        ...baseData,
        status: 'timeout' as const,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={timeoutData}
          onEvent={mockOnEvent}
        />
      );

      const card = screen.getByTestId('decision-card');
      expect(card.getAttribute('data-status')).toBe('timeout');
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Timed Out');
    });

    it('should display skipped status badge when status is skipped', () => {
      const skippedData = {
        ...baseData,
        status: 'skipped' as const,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={skippedData}
          onEvent={mockOnEvent}
        />
      );

      const card = screen.getByTestId('decision-card');
      expect(card.getAttribute('data-status')).toBe('skipped');
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Skipped');
    });

    it('should display status icon', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('status-icon')).toBeInTheDocument();
    });
  });

  describe('Option Selection', () => {
    it('should select an option when clicked', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      const option = screen.getByTestId('option-postgres');
      fireEvent.click(option);

      expect(option.getAttribute('data-selected')).toBe('true');
      expect(screen.getByTestId('selected-icon-postgres')).toBeInTheDocument();
    });

    it('should show unselected icon for unselected options', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('unselected-icon-postgres')).toBeInTheDocument();
      expect(screen.getByTestId('unselected-icon-mongodb')).toBeInTheDocument();
      expect(screen.getByTestId('unselected-icon-redis')).toBeInTheDocument();
    });

    it('should emit SELECT event when option is clicked', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      const option = screen.getByTestId('option-mongodb');
      fireEvent.click(option);

      expect(mockOnEvent).toHaveBeenCalledWith(
        'select',
        expect.objectContaining({
          decisionId: 'dec-123',
          question: baseData.question,
          optionId: 'mongodb',
        })
      );
    });

    it('should call onSelect callback when option is clicked', () => {
      const dataWithCallback = {
        ...baseData,
        onSelect: mockOnSelect,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithCallback}
          onEvent={mockOnEvent}
        />
      );

      const option = screen.getByTestId('option-redis');
      fireEvent.click(option);

      expect(mockOnSelect).toHaveBeenCalledWith('redis');
    });

    it('should allow changing selection', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      // Select first option
      fireEvent.click(screen.getByTestId('option-postgres'));
      expect(screen.getByTestId('option-postgres').getAttribute('data-selected')).toBe('true');

      // Select second option
      fireEvent.click(screen.getByTestId('option-mongodb'));
      expect(screen.getByTestId('option-mongodb').getAttribute('data-selected')).toBe('true');
      expect(screen.getByTestId('option-postgres').getAttribute('data-selected')).toBe('false');
    });

    it('should not allow selection when status is decided', () => {
      const decidedData = {
        ...baseData,
        status: 'decided' as const,
        selectedOptionId: 'postgres',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={decidedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('options-section')).not.toBeInTheDocument();
    });

    it('should not allow selection when status is timeout', () => {
      const timeoutData = {
        ...baseData,
        status: 'timeout' as const,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={timeoutData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('options-section')).not.toBeInTheDocument();
    });

    it('should not allow selection when status is skipped', () => {
      const skippedData = {
        ...baseData,
        status: 'skipped' as const,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={skippedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('options-section')).not.toBeInTheDocument();
    });

    it('should initialize with selectedOptionId if provided', () => {
      const dataWithSelection = {
        ...baseData,
        selectedOptionId: 'mongodb',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithSelection}
          onEvent={mockOnEvent}
        />
      );

      const option = screen.getByTestId('option-mongodb');
      expect(option.getAttribute('data-selected')).toBe('true');
    });
  });

  describe('Submit Button', () => {
    it('should render submit button when status is pending', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('submit-section')).toBeInTheDocument();
      expect(screen.getByTestId('submit-button')).toBeInTheDocument();
    });

    it('should disable submit button when no option is selected', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('submit-button')).toBeDisabled();
    });

    it('should enable submit button when option is selected', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      fireEvent.click(screen.getByTestId('option-postgres'));

      expect(screen.getByTestId('submit-button')).not.toBeDisabled();
    });

    it('should emit SUBMIT event when submit button is clicked', async () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      fireEvent.click(screen.getByTestId('option-postgres'));

      const submitButton = screen.getByTestId('submit-button');
      act(() => {
        fireEvent.click(submitButton);
      });

      await waitFor(() => {
        expect(mockOnEvent).toHaveBeenCalledWith(
          'submit',
          expect.objectContaining({
            decisionId: 'dec-123',
            question: baseData.question,
            optionId: 'postgres',
          })
        );
      });
    });

    it('should call onRespond callback when submit button is clicked', async () => {
      const dataWithCallback = {
        ...baseData,
        onRespond: mockOnRespond,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithCallback}
          onEvent={mockOnEvent}
        />
      );

      fireEvent.click(screen.getByTestId('option-mongodb'));

      const submitButton = screen.getByTestId('submit-button');
      act(() => {
        fireEvent.click(submitButton);
      });

      await waitFor(() => {
        expect(mockOnRespond).toHaveBeenCalledWith({
          optionId: 'mongodb',
          reasoning: undefined,
        });
      });
    });

    it('should not render submit button when status is decided', () => {
      const decidedData = {
        ...baseData,
        status: 'decided' as const,
        selectedOptionId: 'postgres',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={decidedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('submit-section')).not.toBeInTheDocument();
    });

    it('should not render submit button when status is timeout', () => {
      const timeoutData = {
        ...baseData,
        status: 'timeout' as const,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={timeoutData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('submit-section')).not.toBeInTheDocument();
    });

    it('should not render submit button when status is skipped', () => {
      const skippedData = {
        ...baseData,
        status: 'skipped' as const,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={skippedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('submit-section')).not.toBeInTheDocument();
    });
  });

  describe('Reasoning Input', () => {
    it('should render reasoning input when reasoningVisible is true', () => {
      const dataWithReasoning = {
        ...baseData,
        reasoningVisible: true,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithReasoning}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('reasoning-section')).toBeInTheDocument();
      expect(screen.getByTestId('reasoning-input')).toBeInTheDocument();
    });

    it('should not render reasoning input when reasoningVisible is false', () => {
      const dataWithoutReasoning = {
        ...baseData,
        reasoningVisible: false,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithoutReasoning}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('reasoning-section')).not.toBeInTheDocument();
    });

    it('should not render reasoning input by default', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('reasoning-section')).not.toBeInTheDocument();
    });

    it('should update reasoning value when typing', () => {
      const dataWithReasoning = {
        ...baseData,
        reasoningVisible: true,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithReasoning}
          onEvent={mockOnEvent}
        />
      );

      const reasoningInput = screen.getByTestId('reasoning-input') as HTMLInputElement;
      fireEvent.change(reasoningInput, { target: { value: 'I chose PostgreSQL for ACID compliance' } });

      expect(reasoningInput.value).toBe('I chose PostgreSQL for ACID compliance');
    });

    it('should include reasoning in submit event payload', async () => {
      const dataWithReasoning = {
        ...baseData,
        reasoningVisible: true,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithReasoning}
          onEvent={mockOnEvent}
        />
      );

      fireEvent.click(screen.getByTestId('option-postgres'));

      const reasoningInput = screen.getByTestId('reasoning-input');
      fireEvent.change(reasoningInput, { target: { value: 'Best for our use case' } });

      const submitButton = screen.getByTestId('submit-button');
      act(() => {
        fireEvent.click(submitButton);
      });

      await waitFor(() => {
        expect(mockOnEvent).toHaveBeenCalledWith(
          'submit',
          expect.objectContaining({
            reasoning: 'Best for our use case',
          })
        );
      });
    });

    it('should include reasoning in onRespond callback', async () => {
      const dataWithCallback = {
        ...baseData,
        reasoningVisible: true,
        onRespond: mockOnRespond,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithCallback}
          onEvent={mockOnEvent}
        />
      );

      fireEvent.click(screen.getByTestId('option-redis'));

      const reasoningInput = screen.getByTestId('reasoning-input');
      fireEvent.change(reasoningInput, { target: { value: 'Fast cache layer needed' } });

      const submitButton = screen.getByTestId('submit-button');
      act(() => {
        fireEvent.click(submitButton);
      });

      await waitFor(() => {
        expect(mockOnRespond).toHaveBeenCalledWith({
          optionId: 'redis',
          reasoning: 'Fast cache layer needed',
        });
      });
    });

    it('should not render reasoning input when status is decided', () => {
      const decidedData = {
        ...baseData,
        status: 'decided' as const,
        selectedOptionId: 'postgres',
        reasoningVisible: true,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={decidedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.queryByTestId('reasoning-section')).not.toBeInTheDocument();
    });
  });

  describe('Loading States', () => {
    it('should disable submit button when loading', () => {
      const loadingData = {
        ...baseData,
        loading: true,
        selectedOptionId: 'postgres',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={loadingData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('submit-button')).toBeDisabled();
    });

    it('should show loading spinner when loading', () => {
      const loadingData = {
        ...baseData,
        loading: true,
        selectedOptionId: 'postgres',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={loadingData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('should disable option selection when loading', () => {
      const loadingData = {
        ...baseData,
        loading: true,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={loadingData}
          onEvent={mockOnEvent}
        />
      );

      const option = screen.getByTestId('option-postgres');
      expect(option).toBeDisabled();
    });

    it('should disable reasoning input when loading', () => {
      const loadingData = {
        ...baseData,
        loading: true,
        reasoningVisible: true,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={loadingData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('reasoning-input')).toBeDisabled();
    });

    it('should show loading spinner after submit button click', async () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
          onEvent={mockOnEvent}
        />
      );

      fireEvent.click(screen.getByTestId('option-postgres'));

      const submitButton = screen.getByTestId('submit-button');
      act(() => {
        fireEvent.click(submitButton);
      });

      expect(submitButton).toBeDisabled();
    });
  });

  describe('Decided State Display', () => {
    it('should show selected decision when status is decided', () => {
      const decidedData = {
        ...baseData,
        status: 'decided' as const,
        selectedOptionId: 'postgres',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={decidedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('selected-decision')).toBeInTheDocument();
      expect(screen.getByTestId('decided-option-label')).toHaveTextContent('PostgreSQL');
    });

    it('should show status message when status is decided', () => {
      const decidedData = {
        ...baseData,
        status: 'decided' as const,
        selectedOptionId: 'postgres',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={decidedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('status-message')).toBeInTheDocument();
      expect(screen.getByTestId('status-message')).toHaveTextContent('Decision has been made');
    });

    it('should show status message when status is timeout', () => {
      const timeoutData = {
        ...baseData,
        status: 'timeout' as const,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={timeoutData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('status-message')).toBeInTheDocument();
      expect(screen.getByTestId('status-message')).toHaveTextContent('Decision has timed out');
    });

    it('should show status message when status is skipped', () => {
      const skippedData = {
        ...baseData,
        status: 'skipped' as const,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={skippedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('status-message')).toBeInTheDocument();
      expect(screen.getByTestId('status-message')).toHaveTextContent('Decision was skipped');
    });

    it('should fallback to option id if label not found in decided state', () => {
      const decidedData = {
        ...baseData,
        status: 'decided' as const,
        selectedOptionId: 'unknown-option',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={decidedData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('decided-option-label')).toHaveTextContent('unknown-option');
    });
  });

  describe('Edge Cases', () => {
    it('should handle missing onEvent callback gracefully', () => {
      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={baseData}
        />
      );

      const option = screen.getByTestId('option-postgres');

      expect(() => {
        fireEvent.click(option);
      }).not.toThrow();
    });

    it('should handle long question text', () => {
      const longQuestion = 'A'.repeat(200);
      const dataWithLongQuestion = {
        ...baseData,
        question: longQuestion,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithLongQuestion}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('decision-question')).toHaveTextContent(longQuestion);
    });

    it('should handle single option', () => {
      const singleOptionData: DecisionCardData = {
        ...baseData,
        options: [{ id: 'only', label: 'Only Option' }],
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={singleOptionData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getByTestId('option-only')).toBeInTheDocument();
      expect(screen.getByTestId('option-label-only')).toHaveTextContent('Only Option');
    });

    it('should handle many options', () => {
      const manyOptionsData: DecisionCardData = {
        ...baseData,
        options: Array.from({ length: 10 }, (_, i) => ({
          id: `opt-${i}`,
          label: `Option ${i + 1}`,
        })),
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={manyOptionsData}
          onEvent={mockOnEvent}
        />
      );

      expect(screen.getAllByTestId(/^option-opt-/)).toHaveLength(10);
    });

    it('should not trigger submit when button is clicked while loading', async () => {
      const loadingData = {
        ...baseData,
        loading: true,
        selectedOptionId: 'postgres',
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={loadingData}
          onEvent={mockOnEvent}
        />
      );

      const submitButton = screen.getByTestId('submit-button');
      fireEvent.click(submitButton);

      await new Promise(resolve => setTimeout(resolve, 100));

      expect(mockOnEvent).not.toHaveBeenCalledWith(
        'submit',
        expect.anything()
      );
    });

    it('should not allow option selection while loading', () => {
      const loadingData = {
        ...baseData,
        loading: true,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={loadingData}
          onEvent={mockOnEvent}
        />
      );

      const option = screen.getByTestId('option-postgres');
      fireEvent.click(option);

      expect(mockOnEvent).not.toHaveBeenCalledWith(
        'select',
        expect.anything()
      );
    });

    it('should handle all status states', () => {
      const statuses: Array<'pending' | 'decided' | 'timeout' | 'skipped'> = ['pending', 'decided', 'timeout', 'skipped'];

      statuses.forEach((status) => {
        const { container } = render(
          <DecisionCard
            type="a2ui.DecisionCard"
            data={{
              ...baseData,
              status,
              selectedOptionId: status === 'decided' ? 'postgres' : undefined,
            }}
            onEvent={mockOnEvent}
          />
        );

        const card = screen.getByTestId('decision-card');
        expect(card.getAttribute('data-status')).toBe(status);

        container.remove();
      });
    });

    it('should handle empty reasoning string correctly', async () => {
      const dataWithReasoning = {
        ...baseData,
        reasoningVisible: true,
        onRespond: mockOnRespond,
      };

      render(
        <DecisionCard
          type="a2ui.DecisionCard"
          data={dataWithReasoning}
          onEvent={mockOnEvent}
        />
      );

      fireEvent.click(screen.getByTestId('option-postgres'));

      const submitButton = screen.getByTestId('submit-button');
      act(() => {
        fireEvent.click(submitButton);
      });

      await waitFor(() => {
        expect(mockOnRespond).toHaveBeenCalledWith({
          optionId: 'postgres',
          reasoning: undefined,
        });
      });
    });
  });
});
