<?php

use App\Http\Controllers\OpenAIImageController;
use Illuminate\Support\Facades\Route;
use App\Events\AnalyzeDocumentByAI;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\File;

// use OpenAI;
use Smalot\PdfParser\Parser;

/*
|--------------------------------------------------------------------------
| Web Routes
|--------------------------------------------------------------------------
|
| Here is where you can register web routes for your application. These
| routes are loaded by the RouteServiceProvider and all of them will
| be assigned to the "web" middleware group. Make something great!
|
*/

Route::get('/', function () {
    return view('welcome');
});





Route::get('/upload', function () {
    return view('upload', [
        'summary' => session('document_summary'), // AI summary result
        'prompt' => session('custom_prompt'),     // User prompt
        'status' => session('status'),            // Upload status
    ]);
});

Route::post('/upload', function (Request $request) {
    $request->validate([
        'document' => 'required|file|mimes:pdf|max:5120', // Only PDFs, max 5MB
        'prompt' => 'required|string|max:1000', // User must enter a prompt
    ]);

    // Store the uploaded file
    $path = $request->file('document')->store('public/uploads');
    $relativePath = str_replace('public/', '', $path);

    // Dispatch AI analysis event with prompt
    event(new AnalyzeDocumentByAI(1, 1, [
        'title' => 'User uploaded document',
        'path' => 'storage/' . $relativePath,
        'custom_prompt' => $request->input('prompt'),
    ]));

    return redirect('/upload')
        ->with('status', 'Document uploaded and analysis started!')
        ->with('custom_prompt', $request->input('prompt'));
});



Route::get('/chat', function () {
    return view('chat');
});

Route::post('/chat', function (Request $request) {
    $request->validate([
        'prompt' => 'required|string|max:2000',
        'document' => 'nullable|file|mimes:pdf|max:5120',
    ]);

    $prompt = $request->input('prompt');
    $pdfContent = '';

    // Handle PDF file if uploaded
    if ($request->hasFile('document')) {
        $path = $request->file('document')->store('temp');
        $parser = new Parser();
        $pdf = $parser->parseFile(storage_path("app/$path"));
        $pdfText = $pdf->getText();
        $pdfContent = substr($pdfText, 0, 3000); // Safe limit
    }

    // Chat history setup
    $history = session('chat_history', []);
    $messages = [['role' => 'system', 'content' => 'You are an intelligent assistant. Provide full code examples and step-by-step instructions like ChatGPT.']];

    foreach ($history as $entry) {
        $messages[] = ['role' => 'user', 'content' => $entry['user']];
        $messages[] = ['role' => 'assistant', 'content' => $entry['ai']];
    }

    // Add current prompt
    $combinedPrompt = $prompt;
    if ($pdfContent) {
        $combinedPrompt = "The user uploaded this document:\n\n$pdfContent\n\nNow answer this:\n\n$prompt";
    }

    $messages[] = ['role' => 'user', 'content' => $combinedPrompt];

    // Call OpenAI
    $client = OpenAI::client(env('OPENAI_API_KEY'));
    $response = $client->chat()->create([
        'model' => 'gpt-3.5-turbo',
        'messages' => $messages,
    ]);

    $reply = $response->choices[0]->message->content ?? 'No response from AI.';

    // Store in session
    $history[] = [
        'user' => $prompt,
        'ai' => $reply,
    ];
    session(['chat_history' => $history]);

    return redirect('/chat');
});

Route::get('/chat/reset', function () {
    session()->forget('chat_history');
    return redirect('/chat');
});






Route::get('/ai-image', [OpenAIImageController::class, 'form'])->name('image.form');
Route::post('/ai-image/generate', [OpenAIImageController::class, 'generateImage'])->name('generate.image');

