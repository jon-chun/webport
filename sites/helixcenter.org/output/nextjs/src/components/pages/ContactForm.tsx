"use client";

import { useState } from "react";

export function ContactForm() {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    message: "",
  });
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // TODO: Integrate with email service (SendGrid, Resend, etc.)
    console.log("Contact form submission:", formData);
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <div className="p-8 bg-green-50 rounded-lg text-center">
        <h3 className="text-xl font-serif mb-2">Thank you!</h3>
        <p className="text-gray-600">
          Your message has been sent. We'll get back to you soon.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-xl space-y-6">
      <div>
        <label htmlFor="name" className="block text-sm font-medium mb-1">
          Name
        </label>
        <input
          id="name"
          type="text"
          required
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-helix-blue"
        />
      </div>

      <div>
        <label htmlFor="email" className="block text-sm font-medium mb-1">
          Email
        </label>
        <input
          id="email"
          type="email"
          required
          value={formData.email}
          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
          className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-helix-blue"
        />
      </div>

      <div>
        <label htmlFor="message" className="block text-sm font-medium mb-1">
          Message
        </label>
        <textarea
          id="message"
          required
          rows={5}
          value={formData.message}
          onChange={(e) =>
            setFormData({ ...formData, message: e.target.value })
          }
          className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-helix-blue"
        />
      </div>

      <button
        type="submit"
        className="px-6 py-3 bg-helix-blue text-white rounded-lg hover:bg-helix-accent transition-colors"
      >
        Send Message
      </button>
    </form>
  );
}
