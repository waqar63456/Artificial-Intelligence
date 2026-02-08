<?php

namespace App\Listeners;

use App\Events\ContinueWorkflow;
use Illuminate\Support\Facades\Log;

class HandleContinueWorkflow
{
    /**
     * Create the event listener.
     */
    public function __construct()
    {
        // Constructor can be empty or used for dependency injection
    }

    /**
     * Handle the event.
     */
    public function handle(ContinueWorkflow $event): void
    {
        Log::info("ContinueWorkflow triggered", [
            'workflow_id' => $event->workflow_id,
            'next_step' => $event->current_step
        ]);

        // Add your logic for the next workflow step here
    }
}
