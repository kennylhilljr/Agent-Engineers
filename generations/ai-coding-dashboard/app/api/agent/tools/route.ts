import { NextRequest, NextResponse } from 'next/server';

/**
 * Agent Tools API Endpoint
 *
 * This endpoint provides a bridge between the Next.js frontend and the Python agent tools.
 * It spawns a Python process to execute tools and returns the results.
 *
 * Note: This is a simplified implementation for demo purposes.
 * In production, you'd want to use a proper Python backend service.
 */

export async function POST(request: NextRequest) {
  try {
    const { tool, params } = await request.json();

    if (!tool) {
      return NextResponse.json(
        { success: false, error: 'Tool name is required' },
        { status: 400 }
      );
    }

    // For demo purposes, we'll call the Python tools via a subprocess
    // In production, you'd use a proper backend service or API
    const { spawn } = await import('child_process');

    return new Promise((resolve) => {
      const pythonProcess = spawn('python3', [
        '-c',
        `
import sys
import json
sys.path.insert(0, './agent')

from tools import (
    read_file, write_file, list_files,
    create_task, update_task, complete_task,
    get_project_state, log_event, get_events,
    reset_state
)

# Parse input
input_data = json.loads(sys.argv[1])
tool_name = input_data['tool']
params = input_data.get('params', {})

# Execute tool
try:
    if tool_name == 'read_file':
        result = read_file(params.get('path', ''))
    elif tool_name == 'write_file':
        result = write_file(params.get('path', ''), params.get('content', ''))
    elif tool_name == 'list_files':
        result = list_files(params.get('directory', '.'), params.get('recursive', False))
    elif tool_name == 'create_task':
        result = create_task(
            params.get('project_id', ''),
            params.get('title', ''),
            params.get('description', ''),
            params.get('category', 'other')
        )
    elif tool_name == 'update_task':
        result = update_task(
            params.get('task_id', ''),
            params.get('project_id', ''),
            params.get('status'),
            params.get('notes', '')
        )
    elif tool_name == 'complete_task':
        result = complete_task(
            params.get('task_id', ''),
            params.get('project_id', ''),
            params.get('result_notes', '')
        )
    elif tool_name == 'get_project_state':
        result = get_project_state(params.get('project_id', ''))
    elif tool_name == 'log_event':
        result = log_event(
            params.get('project_id', ''),
            params.get('event_type', ''),
            params.get('details', {})
        )
    elif tool_name == 'get_events':
        result = get_events(
            params.get('project_id', ''),
            params.get('event_type'),
            params.get('limit', 50)
        )
    elif tool_name == 'reset_state':
        from tools import reset_state
        reset_state()
        result = {'success': True, 'data': {'message': 'State reset successfully'}}
    else:
        result = {'success': False, 'error': f'Unknown tool: {tool_name}'}

    # Convert result to dict if needed
    if hasattr(result, 'model_dump'):
        result = result.model_dump()

    print(json.dumps(result))
except Exception as e:
    print(json.dumps({
        'success': False,
        'error': str(e)
    }))
`,
        JSON.stringify({ tool, params }),
      ]);

      let output = '';
      let errorOutput = '';

      pythonProcess.stdout.on('data', (data) => {
        output += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      pythonProcess.on('close', (code) => {
        if (code !== 0) {
          resolve(
            NextResponse.json(
              {
                success: false,
                error: `Python process exited with code ${code}`,
                details: errorOutput,
              },
              { status: 500 }
            )
          );
          return;
        }

        try {
          const result = JSON.parse(output.trim());
          resolve(NextResponse.json(result));
        } catch (e) {
          resolve(
            NextResponse.json(
              {
                success: false,
                error: 'Failed to parse Python output',
                output: output,
                stderr: errorOutput,
              },
              { status: 500 }
            )
          );
        }
      });

      // Set timeout
      setTimeout(() => {
        pythonProcess.kill();
        resolve(
          NextResponse.json(
            { success: false, error: 'Tool execution timeout' },
            { status: 504 }
          )
        );
      }, 30000); // 30 second timeout
    });
  } catch (error) {
    console.error('Agent tools API error:', error);
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    message: 'Agent Tools API',
    version: '1.0.0',
    available_tools: [
      'read_file',
      'write_file',
      'list_files',
      'create_task',
      'update_task',
      'complete_task',
      'get_project_state',
      'log_event',
      'get_events',
      'reset_state',
    ],
  });
}
