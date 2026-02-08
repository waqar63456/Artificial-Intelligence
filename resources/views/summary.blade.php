<!DOCTYPE html>
<html>
<head>
    <title>Document Summary</title>
</head>
<body>
    <h1>Document Summary</h1>

     @if(session('document_summary'))
        <h3>AI Summary:</h3>
        <p style="white-space: pre-wrap;">{{ session('document_summary') }}</p>
        
    @endif
</body>
</html>
