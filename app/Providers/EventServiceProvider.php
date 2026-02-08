<?php

namespace App\Providers;


use Illuminate\Foundation\Support\Providers\EventServiceProvider as ServiceProvider;
use App\Events\AnalyzeDocumentByAI;
use App\Events\ContinueWorkflow;

use App\Listeners\HandleAnalyzeDocumentByAI;
use App\Listeners\HandleContinueWorkflow;


class EventServiceProvider extends ServiceProvider
{
    protected $listen = [
        AnalyzeDocumentByAI::class => [
            HandleAnalyzeDocumentByAI::class,
        ],
          ContinueWorkflow::class => [
        HandleContinueWorkflow::class,
    ],
    ];

    public function boot(): void
    {
        //
    }
}
