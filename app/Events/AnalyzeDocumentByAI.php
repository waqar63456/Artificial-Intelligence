<?php

namespace App\Events;

use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class AnalyzeDocumentByAI
{
    use Dispatchable, SerializesModels;

    public $workflow_id;
    public $current_step;
    public $task;

    public function __construct($workflow_id, $current_step, $task)
    {
        $this->workflow_id = $workflow_id;
        $this->current_step = $current_step;
        $this->task = $task;
    }
}
