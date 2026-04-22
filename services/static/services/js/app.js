function loadPage(page, el=null) {
    const content = document.getElementById('content');

    // loading
    content.innerHTML = "<p>Loading...</p>";

    fetch(`/load-${page}/`)
    .then(response => {
        if (!response.ok) {
            throw new Error("Gagal load halaman");
        }
        return response.text();
    })
    .then(html => {
        content.innerHTML = html;

        // aktifkan menu
        document.querySelectorAll('.sidebar li').forEach(li => {
            li.classList.remove('active');
        });

        if (el) {
            el.classList.add('active');
        }
    })
    .catch(error => {
        content.innerHTML = "<p style='color:red;'>Error load halaman</p>";
        console.error(error);
    });
}