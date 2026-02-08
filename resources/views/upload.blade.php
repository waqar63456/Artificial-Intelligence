<!DOCTYPE html>
<html>
<head>
    <title>Upload Document</title>
</head>
<body>
    <h1>Upload Document for Analysis</h1>
<form action="/upload" method="POST" enctype="multipart/form-data">
    @csrf

    <label for="document">Upload PDF:</label><br>
    <input type="file" name="document" required><br><br>

    <label for="prompt">Enter Your Prompt:</label><br>
    <textarea name="prompt" rows="4" cols="50" placeholder="e.g., Summarize in 5 points..." required>{{ old('prompt') }}</textarea><br><br>

    <button type="submit">Submit</button>
</form>

@if(session('status'))
    <p><strong>Status:</strong> {{ session('status') }}</p>
@endif

@if(session('prompt'))
    <p><strong>Your Prompt:</strong> {{ session('prompt') }}</p>
@endif

@if(session('summary'))
    <h3>AI Summary:</h3>
    <pre>{{ session('summary') }}</pre>
@endif


    <br><br><br>

    @if(session('document_summary'))
        <h3>AI Summary:</h3>
        <p style="white-space: pre-wrap;">{{ session('document_summary') }}</p>
        
    @endif

</body>
</html>
