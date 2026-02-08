<?php

namespace App\Events;

class ContinueWorkflow
{
    public int $workflow_id;
    public int $current_step;

    public function __construct(int $workflow_id, int $current_step)
    {
        $this->workflow_id = $workflow_id;
        $this->current_step = $current_step;
    }
}
