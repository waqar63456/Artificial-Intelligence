<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI Chat</title>

    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

    <!-- Highlight.js CSS (Colorful Theme) -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css">

    <!-- Highlight.js Script -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
    <script>hljs.highlightAll();</script>

    <style>
        pre code {
            font-size: 0.9rem;
            line-height: 1.4;
            border-radius: 8px;
            display: block;
            overflow-x: auto;
            padding: 1em;
        }
    </style>
</head>
<body class="bg-light">
<div class="container mt-5">
    <h2 class="mb-4">Ask AI (Code + Instructions)</h2>

    <form action="/chat" method="POST" enctype="multipart/form-data" class="mb-4">
        @csrf
        <div class="mb-3">
            <label for="prompt" class="form-label">Your Prompt</label>
            <textarea name="prompt" id="prompt" rows="4" class="form-control" placeholder="Ask anything">{{ old('prompt') }}</textarea>
        </div>

        <div class="mb-3">
            <label for="document" class="form-label">Optional PDF Document</label>
            <input type="file" name="document" id="document" class="form-control">
        </div>

        <button type="submit" class="btn btn-primary">Ask AI</button>
    </form>

    <hr>

    @if(session('chat_history'))
        <h4>Chat History</h4>
        @foreach(session('chat_history') as $entry)
            <div class="mb-3">
                <strong>You:</strong>
                <pre><code class="plaintext">{{ $entry['user'] }}</code></pre>

                <strong>AI:</strong>
                <pre><code>{{ $entry['ai'] }}</code></pre> <!-- Highlight.js will auto-detect -->
 <!-- You can change language dynamically if needed -->
            </div>
        @endforeach
    @endif
</div>

@if(Session::has('image_url'))
    <h2>Generated Image:</h2>
    <img src="{{ Session::get('image_url') }}" alt="AI Generated Image" style="max-width: 100%;">
@endif

@if(Session::has('document_summary'))
    <h4>AI Summary:</h4>
    <pre><code class="plaintext">{{ Session::get('document_summary') }}</code></pre>
@endif

</body>
</html>
