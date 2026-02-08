<?php

namespace App\Listeners;

use App\Events\AnalyzeDocumentByAI;
use Illuminate\Support\Facades\Log;

class ProcessDocumentByAI
{
    /**
     * Handle the event.
     */
    public function handle(AnalyzeDocumentByAI $event): void
    {
        // Simulate AI document processing
        Log::info('Analyzing document...', [
            'workflow_id' => $event->workflow_id,
            'current_step' => $event->current_step,
            'task' => $event->task,
        ]);

        // Simulate extracting data (e.g., pretend we extracted something)
        Log::info("Document analyzed: " . $event->task['path']);

        // Simulate moving to next step
        $nextStep = $event->current_step + 1;

        Log::info("Moving to next step: " . $nextStep);

        // Trigger the next step in workflow
        // We'll limit steps to avoid infinite loop in this example
        if ($nextStep <= 3) {
            event(new AnalyzeDocumentByAI(
                $event->workflow_id,
                $nextStep,
                $event->task
            ));
        }
    }
}
